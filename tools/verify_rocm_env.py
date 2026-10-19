import os
import subprocess
import sys
import torch

print("=== Python / Torch ===")
print("python:", sys.version.replace("\n", " "))
print("torch:", torch.__version__)
print("torch.version.hip:", getattr(torch.version, "hip", None))
print("torch.version.cuda:", getattr(torch.version, "cuda", None))

print("\n=== CUDA/HIP visibility ===")
print("torch.cuda.is_available():", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device_count:", torch.cuda.device_count())
    print("current_device:", torch.cuda.current_device())
    print("device_name:", torch.cuda.get_device_name(0))

print("\n=== Basic tensor smoke test ===")
if torch.cuda.is_available():
    x = torch.randn(4096, device="cuda")
    y = (x * 2.0 + 1.0).mean()
    torch.cuda.synchronize()
    print("smoke_test_mean:", y.item())
else:
    print("No GPU visible to torch.")

print("\n=== FP dtype support ===")
for dtype in [torch.float32, torch.float16, torch.bfloat16]:
    try:
        t = torch.randn((1024,), device="cuda", dtype=dtype)
        z = (t * 2).mean()
        torch.cuda.synchronize()
        print(f"{dtype}: OK ({z.item()})")
    except Exception as e:
        print(f"{dtype}: FAIL ({type(e).__name__}: {e})")

print("\n=== Optional rocm-sdk CLI ===")
for cmd in (["rocm-sdk", "--help"], ["rocminfo"], ["hipconfig"]):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        print(f"{' '.join(cmd)} -> rc={result.returncode}")
        first = (result.stdout or result.stderr).splitlines()
        if first:
            print(" ", first[0])
    except Exception as e:
        print(f"{' '.join(cmd)} -> not available ({e})")