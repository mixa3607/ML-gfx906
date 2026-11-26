# Strata gfx906

[Strata](https://github.com/Niko1221/Strata) inference image for AMD `gfx906`.
The engine, the Hy4-Flash engine and a picture reader are built from source into
the image; model weights are downloaded separately.

## Build

Requires Docker Buildx and a ROCm base image that still ships gfx906 kernels
(see [ROCm](../rocm/README.md)); the current image builds on
`docker.io/mixa3607/rocm-gfx906:10.1-complete`.

The recipe is the gfx906 source build of
[`docs/AMD_HIP.md`](https://github.com/Niko1221/Strata/blob/v0.2.22/docs/AMD_HIP.md):
`-DSTRATA_HIP_GFX906=ON` on `engine/`, a reader from `terminal/tools/vision`,
both packaged with `tools/packaging/package_engine.py`.

`engine/` is configured with `-DSTRATA_BUILD_INKLING=OFF`: `STRATA_HIP_GFX906`
forces `STRATA_ENABLE_CUDA` on (every `.cu` is compiled as HIP) and the
`src/inkling2` subproject, new after `v0.2.16` and on by default, reacts to that
flag with `enable_language(CUDA)` and stops configure at `Failed to find nvcc`.
The image does not package `strata-inkling`, and upstream's own
`tools/docker/Dockerfile.src` exposes the same switch as `BUILD_INKLING`.

The current preset is Strata `v0.2.22`, built with
`build-context/patch/v0.2.22.patch`. Since `v0.2.17` upstream maps the two HIP
stream-priority aliases the gfx906 build uses and lists `gfx906` in the
architectures the Terminal accepts, both of them fixes from the
`shjszwh/mi50-Strata` fork, so the patch carries only what is still missing:
`cudaDeviceGetP2PAttribute`, `cudaDeviceP2PAttr`,
`cudaDevP2PAttrNativeAtomicSupported` and `cudaDeviceGetPCIBusId`, which the
peer-access code added after `v0.2.16` uses
(`engine/src/core/peer_experts.cpp`). It also keeps `strata-hy4`'s GPU sources
(`*.hip.cpp`, HIP code already) from being handed to nvcc on gfx906: with
`STRATA_HIP_GFX906` the `STRATA_ENABLE_CUDA` flag that selects them would pick
`LANGUAGE CUDA` (`engine/CMakeLists.txt:968`). `build-context/patch/empty.patch`
is for a release that needs none; a release that needs another one gets a patch
file named after it and a preset bump.

## Hy4-Flash engine

`STRATA_BUILD_HY4=1` (the default) builds `strata-hy4` next to `strata` and
packages it as its own component (`0.1.69-…-hip-gfx906-hy4`,
`package_engine.py --shape hy4`), which is the layout upstream's release images
use. `0` builds and ships `strata` alone.

The engine is built, packaged and start-checked (`strata-hy4 --version` in the
image); it has **not** been run on a gfx906 card, so the wave64 code paths
(`HY4_DEV_WMMA` is 0 there, `HY4_HAVE_SDOT4` is 1; `engine/src/hy4flash/run/hy4_gpu.h`)
are compiled but unverified. Run it with `strata-hy4 --gpus 0,1` as
[`docs/AMD_HIP.md`](https://github.com/Niko1221/Strata/blob/v0.2.22/docs/AMD_HIP.md#hy4-flash-experts-on-multiple-amd-gpus)
describes. A package with no picture reader is what a shape component gets, so
the image's component check starts `strata-hy4` instead of requiring a reader.

`STRATA_PICTURE_READER` picks the reader the component carries:

| Value | Reader in the package | Use |
| --- | --- | --- |
| `cpu` (default) | `strata-vision` | Pictures are read on the processor |
| `gpu` | `strata-vision-hip` | `terminal/tools/vision` with `STRATA_VISION_HIP` |
| `both` | both programs | Upstream's AMD package layout |

`cpu` is the default because the reader the Terminal picks is the CPU one on a
card under 24 GB of VRAM, and gfx906 cards are 16 GB (MI50, Radeon VII) or 32 GB
(MI60); upstream also checks pictures on no gfx906 card. A package with only
`strata-vision-hip` makes the Terminal turn pictures off on a 16 GB card (its
`Pictures could not be switched on` line), so the CPU reader is required, not
optional, and the build fails when the reader it was asked for is missing.

Log in to the destination registry and run from this directory:

```bash
export STRATA_IMAGE=registry.arkprojects.space/apps/strata-gfx906
export STRATA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
./build-and-push.image.sh
```

## Run

[upstream Docker documentation](https://github.com/Niko1221/Strata/blob/v0.2.22/docs/DOCKER.md).

`docker-compose.example.yaml` starts the Strata engine;
`docker-compose.hy4.example.yaml` starts the Hy4-Flash engine from the component
this image carries, and has a one-shot `hy4-info` service that only reads the
model header and the Vision shard (`strata-hy4 --info`, no server).

### Pictures

Pictures are on by default and read on the CPU: `strata-vision` needs nothing
from the ROCm runtime, takes no VRAM from the experts (the GPU reader keeps about
1-1.4 GB) and costs a few seconds per picture instead of a fraction of one.

- `VISION=cpu` (or `strata launch --vision cpu`) forces the CPU reader;
  `VISION=off` turns pictures off; `VISION=on` takes the Terminal's default.
- The reader weights (`mmproj`, about 0.9 GB) are the family's pinned projector
  (`terminal/strata_control/pictures.py`): families `qwen`, `coder`, `unsloth` and
  `gyro` read `mmproj-Qwen3.8-Flash-Next-BF16.gguf`, family `swift` reads
  `mmproj-Swift-Qwen3.8-Flash-Next-BF16.gguf`. A copy of that same file under
  another name, in the model folder or the folder above it, is accepted (same
  size, then the pinned SHA-256 is checked); a projector of another model is not
  used, whatever its name is, and pictures stay off for it.
- The CPU reader is built for an AVX2 baseline (its kernels pick a tier at run
  time), so the machine must be Haswell or newer. An older CPU needs
  `-DSTRATA_PORTABLE=OFF -DSTRATA_ISA_FLOOR=avx` on the CPU build in the
  Dockerfile.
- A running container keeps its prepared settings: after this reader appears,
  the Terminal re-runs setup because the saved settings still say pictures are
  off. When it does not, start once with `VISION=cpu`.

> AI生成
