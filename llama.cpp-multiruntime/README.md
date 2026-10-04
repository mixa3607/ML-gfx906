# llama.cpp multiruntime

A single llama.cpp image with CPU, RPC, ROCm (gfx906), and CUDA (sm120) backends.

The [ROCm llama.cpp image](../llama.cpp/README.md) provides the application and
CPU/RPC/HIP backends. The CUDA backend and its runtime libraries are copied from
the CUDA llama.cpp image. Both source images must contain compatible llama.cpp
builds; the NVIDIA driver is provided by the container runtime.

## Build

Requires Docker with buildx and access to both source images. Select a preset
and build:

```bash
. ./llama.cpp-multiruntime/preset.v0.5.0-rocm-7.14-cuda-13.3.0.sh
./llama.cpp-multiruntime/build-and-push.image.sh
```

Defaults are in [`env.sh`](./env.sh); environment variables can override them
after sourcing the preset. Set `LLAMA_PUSH=0` to build without pushing, or
`LLAMA_FORCE_BUILD=1` to rebuild an existing tag. Build logs go to `logs/`.
