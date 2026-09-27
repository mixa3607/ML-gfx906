"""Apply runtime workarounds before ComfyUI imports torch."""

try:
    # amdsmi must be loaded before the ROCm libraries bundled with torch,
    # otherwise torch.cuda.device_count() (amdsmi path since torch 2.13)
    # reports 0 devices.
    import amdsmi

    amdsmi.amdsmi_init()
except Exception:
    pass

try:
    import torch

    if torch.version.hip:
        from torch._native.registry import deregister_op_overrides

        # Bundled native CUDA overrides use Triton kernels that cannot target
        # gfx906. Their registered ATen fallbacks remain available.
        deregister_op_overrides(disable_dispatch_keys="CUDA")
        print("Disabled PyTorch native Triton CUDA overrides for gfx906")
except (ImportError, RuntimeError):
    pass
