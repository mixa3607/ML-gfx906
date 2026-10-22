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
. ./llama.cpp-multiruntime/preset.v0.6.0-rocm-7.14-cuda-13.4.2.sh
./llama.cpp-multiruntime/build-and-push.image.sh
```

The build log is saved to `./logs/build_<timestamp>.log`.

### DeepSeek V4.1 / Unsloth merged source

Both backends use Unsloth release `b11734-mix-c208e5f`, merged commit
`216986d878fef66046afe106ff475817a5c9a59f` (not the release's Git tag).
The source archive SHA256 is
`f125594cd33710a1971caa4c0408cec6d0065d3140bad70a4137e602c150a0fb`.
The application and ROCm 10.1 backend come from `ML-gfx906/llama.cpp`;
the CUDA 13.4.2 SM120 backend comes from `ML-sm120/llama.cpp`.

```bash
. ./llama.cpp-multiruntime/preset.b11734-mix-c208e5f-rocm-10.1-cuda-13.4.2-unsloth.sh
LLAMA_IMAGE=registry.arkprojects.space/apps/llama.cpp-multiruntime \
  REPO_GIT_REF=fix-mix-source ./llama.cpp-multiruntime/build-and-push.image.sh
```

This only builds and publishes an image; it does not restart running pods.

Published image:
`registry.arkprojects.space/apps/llama.cpp-multiruntime:b11734-mix-c208e5f-rocm-10.1-cuda-13.4.2-unsloth-fix-mix-source-pre`
with digest `sha256:a1bf909903afd7fe249e710326f96c18d6a0c756fdd655e45f08ce23e07c99d7`.
Both source images report build 11734, commit `216986d87`. The combined image
passes dynamic symbol resolution for HIP, CUDA and RPC backends (using a CUDA
driver stub only in the smoke-test stage). GPU inference was not exercised.
