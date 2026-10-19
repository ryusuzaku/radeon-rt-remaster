import torch
import time

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("device:", device)
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))

x = torch.randn((4096, 4096), device=device, dtype=torch.float16)
y = torch.randn((4096, 4096), device=device, dtype=torch.float16)

if device.type == "cuda":
    torch.cuda.synchronize()
t0 = time.perf_counter()
z = x @ y
if device.type == "cuda":
    torch.cuda.synchronize()
t1 = time.perf_counter()

print("z.device:", z.device)
if device.type == "cuda":
    print("mem_alloc_mb:", torch.cuda.memory_allocated() / 1024**2)
print("time:", t1 - t0)