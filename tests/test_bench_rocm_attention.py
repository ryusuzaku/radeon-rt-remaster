"""CPU-only tests for the ROCm benchmark's SDPA backend selection.

`bench_rocm.py` imports torch at module level, so a small stub stands in for
it here. The stub deliberately exposes no `torch.backends`, which also pins
the regression: importing the benchmark must not toggle any SDPA backend.
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
STUB_MODULES = (
    "torch",
    "torch.nn",
    "torch.nn.functional",
    "torch.nn.utils",
    "torch.nn.utils.parametrizations",
)

_bench_rocm = None


def _install_stub_torch():
    torch = types.ModuleType("torch")
    torch.__version__ = "stub"
    torch.dtype = type("dtype", (), {})
    torch.Tensor = type("Tensor", (), {})
    torch.float16 = "float16"
    torch.bfloat16 = "bfloat16"
    torch.float32 = "float32"
    torch.device = lambda spec: types.SimpleNamespace(type=spec)
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    torch.version = types.SimpleNamespace(hip=None, cuda=None)

    nn = types.ModuleType("torch.nn")
    nn.Module = object
    functional = types.ModuleType("torch.nn.functional")
    utils = types.ModuleType("torch.nn.utils")
    parametrizations = types.ModuleType("torch.nn.utils.parametrizations")
    parametrizations.weight_norm = lambda module: module

    nn.functional = functional
    nn.utils = utils
    utils.parametrizations = parametrizations
    torch.nn = nn

    sys.modules.update(
        {
            "torch": torch,
            "torch.nn": nn,
            "torch.nn.functional": functional,
            "torch.nn.utils": utils,
            "torch.nn.utils.parametrizations": parametrizations,
        }
    )


def _load_bench_rocm():
    global _bench_rocm
    if _bench_rocm is not None:
        return _bench_rocm

    saved = {name: sys.modules.get(name) for name in STUB_MODULES}
    saved_bench = sys.modules.get("bench_rocm")
    try:
        _install_stub_torch()
        spec = importlib.util.spec_from_file_location(
            "bench_rocm", TOOLS / "bench_rocm.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["bench_rocm"] = module
        spec.loader.exec_module(module)
        _bench_rocm = module
        return module
    finally:
        for name, previous in saved.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
        if saved_bench is None:
            sys.modules.pop("bench_rocm", None)
        else:
            sys.modules["bench_rocm"] = saved_bench


class FakeCudaBackends:
    def __init__(self):
        self.calls = []
        self.state = {}

    def enable_flash_sdp(self, enabled):
        self.calls.append(("flash", enabled))
        self.state["flash"] = enabled

    def enable_mem_efficient_sdp(self, enabled):
        self.calls.append(("mem_efficient", enabled))
        self.state["mem_efficient"] = enabled

    def enable_math_sdp(self, enabled):
        self.calls.append(("math", enabled))
        self.state["math"] = enabled


class AttentionBackendSelectionTests(unittest.TestCase):
    def setUp(self):
        self.bench = _load_bench_rocm()

    def test_import_does_not_configure_backends(self):
        # The stub torch has no `backends`; a return of the old import-time
        # toggles would make loading the module fail before this assertion.
        self.assertFalse(hasattr(self.bench.torch, "backends"))

    def test_each_choice_selects_one_path(self):
        expected = {
            "auto": {"flash": True, "mem_efficient": True, "math": True},
            "flash": {"flash": True, "mem_efficient": False, "math": False},
            "mem-efficient": {"flash": False, "mem_efficient": True, "math": False},
            "math": {"flash": False, "mem_efficient": False, "math": True},
        }
        for choice, state in expected.items():
            with self.subTest(choice=choice):
                backends = FakeCudaBackends()
                self.assertEqual(
                    self.bench.apply_attention_backend(backends, choice), state
                )
                self.assertEqual(backends.state, state)

    def test_unknown_choice_rejected_before_touching_backends(self):
        backends = FakeCudaBackends()
        with self.assertRaises(ValueError):
            self.bench.apply_attention_backend(backends, "bogus")
        self.assertEqual(backends.calls, [])

    def test_resolution_precedence(self):
        env = {self.bench.ATTENTION_BACKEND_ENV: "flash"}
        self.assertEqual(self.bench.resolve_attention_backend(None, {}), "auto")
        self.assertEqual(self.bench.resolve_attention_backend(None, env), "flash")
        self.assertEqual(self.bench.resolve_attention_backend("math", env), "math")
        self.assertEqual(
            self.bench.resolve_attention_backend(None, {self.bench.ATTENTION_BACKEND_ENV: " Math "}),
            "math",
        )

    def test_resolution_rejects_unknown_env(self):
        with self.assertRaises(ValueError):
            self.bench.resolve_attention_backend(
                None, {self.bench.ATTENTION_BACKEND_ENV: "cudnn"}
            )

    def test_child_cli_stays_compatible(self):
        args = self.bench.build_arg_parser().parse_args(
            ["--child", "linear", "[1, 2]", "float16"]
        )
        self.assertEqual(args.child, ["linear", "[1, 2]", "float16"])
        self.assertIsNone(args.attn_backend)

    def test_backend_flag_after_child(self):
        args = self.bench.build_arg_parser().parse_args(
            ["--child", "linear", "[1, 2]", "float16", "--attn-backend", "flash"]
        )
        self.assertEqual(args.attn_backend, "flash")


if __name__ == "__main__":
    unittest.main()
