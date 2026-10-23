# bench_rocm_windows_fixed.py
import os

# ----------------------------
# ROCm / MIOpen env
# ----------------------------
WORKSPACE_LIMIT = 1024 * 1024 * 1024  # 1 GiB

os.environ["AMD_SERIALIZE_KERNEL"] = "0"
#os.environ["MIOPEN_FIND_MODE"] = "1"
#os.environ["MIOPEN_FIND_ENFORCE"] = "1"
os.environ["MIOPEN_CONVOLUTION_MAX_WORKSPACE"] = str(WORKSPACE_LIMIT)

# Optional debug:
# os.environ["HIP_LAUNCH_BLOCKING"] = "1"
# os.environ["TORCH_ROCM_FA_PREFER_CK"] = "1"

import argparse
import gc
import json
import subprocess
import sys
import time
import traceback

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.nn.utils.parametrizations import weight_norm

# ----------------------------
# Config
# ----------------------------
B = 8
ISOLATE_BASE_OPS = True
ISOLATE_HEAVY_OPS = True
CHILD_TIMEOUT_SEC = 180

# ----------------------------
# SDPA backend selection
# The benchmark includes SDPA/transformer layers, so the backend has to be
# chosen deliberately instead of being disabled globally. "auto" leaves all
# backends enabled and lets PyTorch pick a kernel per call.
# ----------------------------
ATTENTION_BACKENDS = ("auto", "flash", "mem-efficient", "math")
DEFAULT_ATTENTION_BACKEND = "auto"
ATTENTION_BACKEND_ENV = "BENCH_ROCM_ATTN_BACKEND"

# choice -> (flash, mem_efficient, math)
_ATTENTION_BACKEND_FLAGS = {
    "auto": (True, True, True),
    "flash": (True, False, False),
    "mem-efficient": (False, True, False),
    "math": (False, False, True),
}


def resolve_attention_backend(cli_value, environ=None):
    """Resolve the backend from CLI > environment > default, validating it."""
    environ = os.environ if environ is None else environ
    value = cli_value or environ.get(ATTENTION_BACKEND_ENV) or DEFAULT_ATTENTION_BACKEND
    value = value.strip().lower()
    if value not in ATTENTION_BACKENDS:
        raise ValueError(
            f"unknown attention backend {value!r}; "
            f"expected one of {', '.join(ATTENTION_BACKENDS)}"
        )
    return value


def apply_attention_backend(cuda_backends, choice):
    """Enable exactly the requested SDPA backend(s) and return the new state."""
    try:
        flash, mem_efficient, math = _ATTENTION_BACKEND_FLAGS[choice]
    except KeyError:
        raise ValueError(
            f"unknown attention backend {choice!r}; "
            f"expected one of {', '.join(ATTENTION_BACKENDS)}"
        ) from None
    cuda_backends.enable_flash_sdp(flash)
    cuda_backends.enable_mem_efficient_sdp(mem_efficient)
    cuda_backends.enable_math_sdp(math)
    return {"flash": flash, "mem_efficient": mem_efficient, "math": math}


def build_arg_parser():
    parser = argparse.ArgumentParser(description="ROCm/AMD GPU micro-benchmark.")
    parser.add_argument(
        "--child",
        nargs=3,
        metavar=("LAYER", "SHAPE", "DTYPE"),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--attn-backend",
        choices=ATTENTION_BACKENDS,
        default=None,
        help=(
            "SDPA backend to measure (default: auto, or "
            f"${ATTENTION_BACKEND_ENV})"
        ),
    )
    return parser


# This does NOT directly pass a workspace pointer into stock PyTorch conv kernels.
# Keep False unless you explicitly want to test memory pressure side-effects.
ALLOCATE_WORKSPACE_TENSOR = False

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
is_cuda = device.type == "cuda"
is_rocm = is_cuda and getattr(torch.version, "hip", None) is not None

workspace_tensor = None


def cleanup() -> None:
    if is_cuda:
        try:
            torch.cuda.synchronize()
        except Exception:
            pass
        try:
            torch.cuda.empty_cache()
        except Exception:
            pass
    gc.collect()


def env_info(attn_backend: str) -> None:
    print("=== Environment ===")
    print("python              :", sys.version.replace("\n", " "))
    print("attn backend        :", attn_backend)
    print("torch               :", torch.__version__)
    print("torch.version.hip   :", getattr(torch.version, "hip", None))
    print("torch.version.cuda  :", getattr(torch.version, "cuda", None))
    print("cuda.is_available   :", torch.cuda.is_available())
    print("AMD_SERIALIZE_KERNEL:", os.environ.get("AMD_SERIALIZE_KERNEL"))
    print("MIOPEN_FIND_MODE    :", os.environ.get("MIOPEN_FIND_MODE"))
    print("MIOPEN_FIND_ENFORCE :", os.environ.get("MIOPEN_FIND_ENFORCE"))
    print("MIOPEN_CONV_MAX_WS  :", os.environ.get("MIOPEN_CONVOLUTION_MAX_WORKSPACE"))
    if torch.cuda.is_available():
        print("device              :", torch.cuda.get_device_name(0))
    print()


def probe_attention_once() -> None:
    print("=== SDPA / Flash attention probe ===")
    try:
        print("flash_sdp_enabled   :", torch.backends.cuda.flash_sdp_enabled())
    except Exception as e:
        print("flash_sdp_enabled   : FAIL", e)

    try:
        print("mem_eff_sdp_enabled :", torch.backends.cuda.mem_efficient_sdp_enabled())
    except Exception as e:
        print("mem_eff_sdp_enabled : FAIL", e)

    try:
        print("math_sdp_enabled    :", torch.backends.cuda.math_sdp_enabled())
    except Exception as e:
        print("math_sdp_enabled    : FAIL", e)

    try:
        print("flash_available     :", torch.backends.cuda.is_flash_attention_available())
    except Exception as e:
        print("flash_available     : FAIL", e)
    print()


def dtype_supported(dtype: torch.dtype) -> bool:
    if not is_cuda:
        return dtype == torch.float32
    try:
        x = torch.randn((1024,), device=device, dtype=dtype)
        y = (x * 2).mean()
        torch.cuda.synchronize()
        _ = y.item()
        return True
    except Exception:
        return False


def prepare_module(mod: nn.Module, dtype: torch.dtype) -> nn.Module:
    return mod.to(device=device, dtype=dtype).eval()


def bench(mod: nn.Module, shape: tuple[int, ...], dtype: torch.dtype, warmup: int = 10, runs: int = 100):
    try:
        cleanup()
        x = torch.randn(shape, dtype=dtype, device=device)

        with torch.inference_mode():
            for _ in range(warmup):
                _ = mod(x)
            if is_cuda:
                torch.cuda.synchronize()

            start = time.perf_counter()
            for _ in range(runs):
                _ = mod(x)
            if is_cuda:
                torch.cuda.synchronize()
            end = time.perf_counter()

        mem_mb = torch.cuda.memory_allocated() / (1024 ** 2) if is_cuda else 0.0
        return {
            "ok": True,
            "ms": ((end - start) / runs) * 1000.0,
            "mem_mb": mem_mb,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "trace": traceback.format_exc(limit=4),
        }

def maybe_weight_norm(mod: nn.Module, enabled: bool) -> nn.Module:
    return weight_norm(mod) if enabled else mod


class BatchedMatmulBlock(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(dim, dim) * (dim ** -0.5))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, M, K), weight: (K, N)
        return torch.matmul(x, self.weight)


class SDPABlock(nn.Module):
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, H, S, D)
        return F.scaled_dot_product_attention(
            x, x, x, dropout_p=0.0, is_causal=False
        )


class RMSNormBlock(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(dim))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        rms = torch.rsqrt(x.pow(2).mean(dim=-1, keepdim=True) + self.eps)
        return x * rms * self.weight


class MLPBlock(nn.Module):
    def __init__(self, dim: int, hidden_dim: int):
        super().__init__()
        self.fc1 = nn.Linear(dim, hidden_dim, bias=True)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(hidden_dim, dim, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc2(self.act(self.fc1(x)))


class HiFiResBlock(nn.Module):
    def __init__(self, channels: int = 256, use_weight_norm: bool = True):
        super().__init__()
        self.c1 = maybe_weight_norm(
            nn.Conv1d(channels, channels, kernel_size=3, padding=1, dilation=1),
            use_weight_norm,
        )
        self.c2 = maybe_weight_norm(
            nn.Conv1d(channels, channels, kernel_size=3, padding=3, dilation=3),
            use_weight_norm,
        )
        self.c3 = maybe_weight_norm(
            nn.Conv1d(channels, channels, kernel_size=3, padding=5, dilation=5),
            use_weight_norm,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        y1 = self.c1(x)
        y2 = self.c2(y1)
        y3 = self.c3(y2)
        return x + y1 + y2 + y3


class TinyTransformerBlock(nn.Module):
    def __init__(self, dim: int = 1024, heads: int = 16, mlp_ratio: int = 4):
        super().__init__()
        assert dim % heads == 0
        self.dim = dim
        self.heads = heads
        self.head_dim = dim // heads

        self.norm1 = nn.LayerNorm(dim)
        self.qkv = nn.Linear(dim, dim * 3, bias=False)
        self.proj = nn.Linear(dim, dim, bias=False)

        self.norm2 = nn.LayerNorm(dim)
        self.fc1 = nn.Linear(dim, dim * mlp_ratio, bias=True)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(dim * mlp_ratio, dim, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, S, D)
        b, s, d = x.shape

        y = self.norm1(x)
        qkv = self.qkv(y).view(b, s, 3, self.heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # (3, B, H, S, Hd)
        q, k, v = qkv[0], qkv[1], qkv[2]

        attn = F.scaled_dot_product_attention(
            q, k, v, dropout_p=0.0, is_causal=False
        )
        attn = attn.permute(0, 2, 1, 3).reshape(b, s, d)
        x = x + self.proj(attn)

        y = self.norm2(x)
        y = self.fc2(self.act(self.fc1(y)))
        return x + y

def make_layers():
    return [
        # ----------------------------
        # Existing
        # ----------------------------
        ("linear", nn.Linear(768, 192, bias=True), (B, 768), 10, 200),

        ("conv1d 192->192 k1", nn.Conv1d(192, 192, kernel_size=1), (B, 192, 200), 10, 200),
        ("conv1d 192->768 k3", nn.Conv1d(192, 768, kernel_size=3), (B, 192, 200), 10, 100),
        ("conv1d 768->192 k3", nn.Conv1d(768, 192, kernel_size=3), (B, 768, 200), 10, 100),

        ("up_0", weight_norm(nn.ConvTranspose1d(512, 256, kernel_size=20, stride=10, padding=5)), (B, 512, 40), 5, 100),
        ("up_1", weight_norm(nn.ConvTranspose1d(256, 128, kernel_size=16, stride=8, padding=4)), (B, 256, 400), 5, 50),
        ("up_2", weight_norm(nn.ConvTranspose1d(128, 64, kernel_size=4, stride=2, padding=1)), (B, 128, 3200), 3, 30),
        ("up_3", weight_norm(nn.ConvTranspose1d(64, 32, kernel_size=4, stride=2, padding=1)), (B, 64, 6400), 3, 30),

        ("dn_0", nn.Conv1d(1, 256, kernel_size=64, stride=32, padding=16), (B, 1, 12800), 5, 50),
        ("dn_1", nn.Conv1d(1, 128, kernel_size=8, stride=4, padding=2), (B, 1, 12800), 5, 50),
        ("dn_2", nn.Conv1d(1, 64, kernel_size=4, stride=2, padding=1), (B, 1, 12800), 5, 50),
        ("dn_3", nn.Conv1d(1, 32, kernel_size=1, stride=1), (B, 1, 12800), 5, 80),

        ("res1a", weight_norm(nn.Conv1d(256, 256, kernel_size=3, stride=1, padding=1)), (B, 256, 400), 5, 50),
        ("res1b", weight_norm(nn.Conv1d(256, 256, kernel_size=3, stride=1, padding=3, dilation=3)), (B, 256, 400), 5, 50),
        ("res1c", weight_norm(nn.Conv1d(256, 256, kernel_size=3, stride=1, padding=5, dilation=5)), (B, 256, 400), 5, 50),

        ("res2a", weight_norm(nn.Conv1d(256, 256, kernel_size=7, stride=1, padding=3)), (B, 256, 400), 5, 50),
        ("res2b", weight_norm(nn.Conv1d(256, 256, kernel_size=7, stride=1, padding=9, dilation=3)), (B, 256, 400), 5, 50),
        ("res2c", weight_norm(nn.Conv1d(256, 256, kernel_size=7, stride=1, padding=15, dilation=5)), (B, 256, 400), 5, 50),

        ("res3a", weight_norm(nn.Conv1d(256, 256, kernel_size=11, stride=1, padding=5)), (B, 256, 400), 5, 50),
        ("res3b", weight_norm(nn.Conv1d(256, 256, kernel_size=11, stride=1, padding=15, dilation=3)), (B, 256, 400), 5, 50),
        ("res3c", weight_norm(nn.Conv1d(256, 256, kernel_size=11, stride=1, padding=25, dilation=5)), (B, 256, 400), 5, 50),

        ("conv_post", nn.Conv1d(32, 1, kernel_size=7, padding=3), (B, 32, 12800), 5, 50),

        # ----------------------------
        # Added: bigger GEMM / matmul
        # ----------------------------
        ("gemm 4096->4096", nn.Linear(4096, 4096, bias=False), (2048, 4096), 5, 50),
        ("gemm 4096->16384", nn.Linear(4096, 16384, bias=False), (1024, 4096), 5, 30),
        ("batched matmul 128", BatchedMatmulBlock(128), (32, 256, 128), 5, 50),

        # ----------------------------
        # Added: norm / MLP
        # ----------------------------
        ("layernorm 1024", nn.LayerNorm(1024), (B, 1024, 1024), 5, 50),
        ("rmsnorm 1024", RMSNormBlock(1024), (B, 1024, 1024), 5, 50),
        ("mlp 1024->4096->1024", MLPBlock(1024, 4096), (4, 256, 1024), 5, 30),

        # ----------------------------
        # Added: SDPA / transformer
        # The active path follows --attn-backend (see apply_attention_backend).
        # ----------------------------
        ("sdpa h16 s512 d64", SDPABlock(), (4, 16, 512, 64), 5, 20),
        ("transformer block 1024", TinyTransformerBlock(dim=1024, heads=16, mlp_ratio=4), (2, 256, 1024), 3, 15),

        # ----------------------------
        # Added: Conv2d / grouped / depthwise
        # ----------------------------
        ("conv2d 64->64 k3", nn.Conv2d(64, 64, kernel_size=3, padding=1), (4, 64, 128, 128), 5, 30),
        ("conv2d grouped g8", nn.Conv2d(64, 64, kernel_size=3, padding=1, groups=8), (4, 64, 128, 128), 5, 30),
        ("conv2d depthwise", nn.Conv2d(64, 64, kernel_size=3, padding=1, groups=64), (4, 64, 128, 128), 5, 30),
        ("deconv2d 64->32", nn.ConvTranspose2d(64, 32, kernel_size=4, stride=2, padding=1), (4, 64, 64, 64), 5, 30),

        # ----------------------------
        # Added: HiFi-style resblock plain vs weight_norm
        # ----------------------------
        ("hifi resblock plain", HiFiResBlock(channels=256, use_weight_norm=False), (B, 256, 400), 5, 40),
        ("hifi resblock wn", HiFiResBlock(channels=256, use_weight_norm=True), (B, 256, 400), 5, 40),
    ]

HEAVY = {
    "linear": [(32, 768), (64, 768)],
    "conv1d 192->192 k1": [(16, 192, 200), (32, 192, 3200)],
    "conv1d 192->768 k3": [(16, 192, 200), (8, 192, 12800)],
    "conv1d 768->192 k3": [(16, 768, 200), (8, 768, 6400)],

    "up_0": [(16, 512, 40), (32, 512, 40)],
    "up_1": [(8, 256, 400), (16, 256, 400)],
    "up_2": [(8, 128, 3200)],
    "up_3": [(8, 64, 6400)],

    "dn_0": [(16, 1, 25600), (32, 1, 51200)],
    "dn_1": [(16, 1, 25600)],
    "dn_2": [(16, 1, 25600)],
    "dn_3": [(16, 1, 25600)],

    "res1a": [(B, 256, 800)],
    "res1b": [(B, 256, 800)],
    "res1c": [(B, 256, 800)],
    "res2a": [(B, 256, 800)],
    "res2b": [(B, 256, 800)],
    "res2c": [(B, 256, 800)],
    "res3a": [(B, 256, 800)],
    "res3b": [(B, 256, 800)],
    "res3c": [(B, 256, 800)],

    "conv_post": [(B, 32, 25600)],

    # Added: GEMM / matmul
    "gemm 4096->4096": [(4096, 4096)],
    "gemm 4096->16384": [(1536, 4096)],
    "batched matmul 128": [(32, 512, 128), (16, 256, 256)],

    # Added: norm / MLP
    "layernorm 1024": [(B, 2048, 1024)],
    "rmsnorm 1024": [(B, 2048, 1024)],
    "mlp 1024->4096->1024": [(4, 512, 1024)],

    # Added: SDPA / transformer
    "sdpa h16 s512 d64": [(4, 16, 1024, 64), (2, 16, 2048, 64)],
    "transformer block 1024": [(2, 512, 1024)],

    # Added: Conv2d
    "conv2d 64->64 k3": [(4, 64, 256, 256)],
    "conv2d grouped g8": [(4, 64, 256, 256)],
    "conv2d depthwise": [(4, 64, 256, 256)],
    "deconv2d 64->32": [(4, 64, 128, 128)],

    # Added: HiFi-style block split
    "hifi resblock plain": [(B, 256, 800)],
    "hifi resblock wn": [(B, 256, 800)],
}

def child(layer_name: str, shape, dtype_name: str) -> int:
    dtype = {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[dtype_name]

    layers = {name: (mod, base_shape, warmup, runs) for name, mod, base_shape, warmup, runs in make_layers()}
    mod, _, warmup, runs = layers[layer_name]

    if not dtype_supported(dtype):
        print(json.dumps({"skip": True}))
        return 0

    mod = prepare_module(mod, dtype)
    result = bench(mod, tuple(shape), dtype, warmup=warmup, runs=runs)
    print(json.dumps(result))
    return 0


def run_child(layer_name: str, shape, dtype_name: str):
    cmd = [sys.executable, "-u", __file__, "--child", layer_name, json.dumps(shape), dtype_name]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=CHILD_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"child timeout after {CHILD_TIMEOUT_SEC}s"}

    stdout = (p.stdout or "").strip()
    stderr = (p.stderr or "").strip()

    if p.returncode != 0:
        return {"ok": False, "error": stderr or stdout or f"child rc={p.returncode}"}

    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return {"ok": False, "error": "child returned no stdout"}

    try:
        return json.loads(lines[-1])
    except Exception as e:
        return {
            "ok": False,
            "error": f"failed to parse child json: {e}; last_line={lines[-1]!r}; stderr={stderr!r}",
        }


def run_case(name: str, mod: nn.Module, shape, dtype: torch.dtype, warmup: int, runs: int, isolate: bool):
    if isolate:
        dtype_name = (
            "float16" if dtype == torch.float16 else
            "bfloat16" if dtype == torch.bfloat16 else
            "float32"
        )
        return run_child(name, shape, dtype_name)
    return bench(mod, tuple(shape), dtype, warmup=warmup, runs=runs)


def print_result(name: str, shape, res) -> None:
    if res.get("skip"):
        print(f"{name:20s} {shape}: SKIP unsupported")
    elif res.get("ok"):
        print(f"{name:20s} {shape}: {res['ms']:.3f} ms | {res.get('mem_mb', 0.0):.1f} MB")
    else:
        print(f"{name:20s} {shape}: FAIL {res.get('error')}")
        if res.get("trace"):
            print(res["trace"])


def main(attn_backend: str) -> None:
    global workspace_tensor

    env_info(attn_backend)

    if not is_cuda:
        print("No GPU visible.")
        return

    if ALLOCATE_WORKSPACE_TENSOR:
        try:
            workspace_tensor = torch.empty(WORKSPACE_LIMIT, dtype=torch.uint8, device=device)
            print(f"workspace_tensor     : allocated {WORKSPACE_LIMIT / (1024**3):.2f} GiB")
        except Exception as e:
            print(f"workspace_tensor     : allocation failed ({type(e).__name__}: {e})")
    else:
        print("workspace_tensor     : disabled")

    probe_attention_once()

    for dtype in [torch.float16, torch.bfloat16]:
        print(f"=== {dtype} ===")
        if not dtype_supported(dtype):
            print("(all layers): SKIP unsupported\n")
            continue

        prepared = []
        for name, mod, shape, warmup, runs in make_layers():
            try:
                prepared.append((name, prepare_module(mod, dtype), shape, warmup, runs))
            except Exception as e:
                print(f"{name:20s} PREPARE FAIL {type(e).__name__}: {e}")

        for name, mod, shape, warmup, runs in prepared:
            res = run_case(name, mod, shape, dtype, warmup, runs, ISOLATE_BASE_OPS)
            print_result(name, shape, res)

            if not res.get("ok"):
                continue

            for heavy_shape in HEAVY.get(name, []):
                heavy_res = run_case(
                    name,
                    mod,
                    heavy_shape,
                    dtype,
                    max(3, warmup // 2),
                    max(20, runs // 2),
                    ISOLATE_HEAVY_OPS,
                )
                print_result(name, heavy_shape, heavy_res)

        print()


if __name__ == "__main__":
    args = build_arg_parser().parse_args()
    try:
        selected_backend = resolve_attention_backend(args.attn_backend)
    except ValueError as exc:
        raise SystemExit(str(exc))

    # Children are fresh interpreters; the environment is what carries the
    # selection into them.
    os.environ[ATTENTION_BACKEND_ENV] = selected_backend
    apply_attention_backend(torch.backends.cuda, selected_backend)

    if args.child:
        layer_name, shape_json, dtype_name = args.child
        raise SystemExit(child(layer_name, tuple(json.loads(shape_json)), dtype_name))
    main(selected_backend)
