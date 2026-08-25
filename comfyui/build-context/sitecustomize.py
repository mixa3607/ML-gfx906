"""Apply runtime workarounds before ComfyUI imports torch."""

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
