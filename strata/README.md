# Strata gfx906

[Strata](https://github.com/Niko1221/Strata) inference image for AMD `gfx906`.
The Qwen engine and its GPU vision encoder are built into the image. A CPU
vision reader is included as the Qwen fallback. Model weights are downloaded
separately.

`FAMILY` selects the model when the container starts. The entrypoint passes
it to `strata launch --family`. This directory's compose example uses
`FAMILY=unsloth` and `MODEL=UD-Q4_K_XL` (Qwen3.8-Flash-Next). `FAMILY=qwen`
is the upstream name for the ISTA-DASLab Qwen packs. DeepSeek-V4.1-Flash is
`FAMILY=deepseek41` and needs the preset below. The daily workflow still
builds the Qwen image from upstream Strata.

## Build

Requires Docker Buildx and the [ROCm base image](../rocm/README.md).
Log in to the destination registry and run from this directory:

```bash
export STRATA_IMAGE=registry.arkprojects.space/apps/strata-gfx906
export STRATA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
./build-and-push.image.sh
```

`STRATA_BUILD_DSV41` stays `0` here, so this image does not compile
`strata-dsv41`.

## DeepSeek V4.1 Flash

Upstream Strata skips `strata-dsv41` on gfx906 until
[pull request 5739](https://github.com/Niko1221/Strata/pull/5739) is merged.
Until then, source the preset. It clones `shjszwh/mi50-Strata` branch
`gfx906-dsv41` and checks out commit
`9898718423ed1f319730fc65bac9a11a17c49988`.

```bash
. preset.deepseek41-rocm-10.1.sh
export STRATA_IMAGE=registry.arkprojects.space/apps/strata-gfx906
./build-and-push.image.sh
```

The Qwen example above also sets
`STRATA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"`.
The MI50 DeepSeek run was built without that flag. Export it when you want
the same HIP scheduling flag as the Qwen image.

The image tag uses `deepseek41-rocm-10.1`. The build adds
`-DSTRATA_BUILD_DSV41=ON` and `-DSTRATA_NATIVE_EXPERTS=ON` to the existing
gfx906 configure (`-DSTRATA_HIP_GFX906=ON`, `-DSTRATA_BUILD_TESTS=OFF`) and
builds both `strata` and `strata-dsv41`. `FAMILY` then selects which one
`strata launch` starts. Base image:
`docker.io/mixa3607/rocm-gfx906:10.1-complete`.

llama.cpp still comes from `setup.get_llama_cpp()` (the tree's pin
`3cf03257`). The engine that was run on MI50 used llama.cpp `cd4ed902`
instead. That tree reports `GGML_TYPE_COUNT` 44, and the trellis overlay
anchors on 43, so the overlay stays off. MMQ on that tree needs
`__has_include("mmid.cuh")`, which the fork already has.

After 5739 is merged, point `STRATA_REPO` back at
`https://github.com/Niko1221/Strata.git` and set `STRATA_COMMIT` to the
merged commit. Keep `STRATA_BUILD_DSV41=1`.

## Run

The entrypoint is the one shipped in the Strata tree
(`docker/entrypoint.sh`). It runs `strata launch` and listens on port 8080.
`strata launch` starts `serve/server.py` in front of the engine that
`FAMILY` selects.

[upstream Docker documentation](https://github.com/Niko1221/Strata/blob/v0.2.3.1/docs/DOCKER.md).

Qwen stays as in [docker-compose.example.yaml](docker-compose.example.yaml).
For DeepSeek, on an image built with the preset:

```yaml
FAMILY: deepseek41
MODEL: IST-DAS-2.00bpw
MODEL_PATH: /models
GPUS: "0,1"
CONTEXT: 256k
VISION: "off"
STRATA_SET: "dspark=none profile-readonly=on"
```

`GPUS=0,1` is `--gpu 0,1`. `CONTEXT=256k` is 262144 tokens, the engine's
`--max-context`. That flag is not a measured quality claim. `VISION=on` and
`VISION=off` are the DeepSeek picture switch. `on` runs the vision tower on
the GPU (the log names it CUDA0) and keeps the tower weights in host memory
between pictures. There is no CPU vision switch. `VISION=cpu` is only the
Qwen reader. Vision GEMM on this card is hipBLAS on the GPU.

The picture file is `mmproj-DeepSeek-V4.1-Flash-1017-BF16.gguf`. The pack
wires it as a relative path. It is not copied into the image. Mount the
model directory read-only and set `MODEL_PATH`.

`STRATA_SET` is the entrypoint's advanced list. Those two values are the
engine flags `--dspark none` and `--profile-readonly` that were used on
MI50.

One machine, two gfx906 cards (`rocminfo` name Radeon Pro VII), monitor
readings from five requests, not a benchmark: a short reply contained
Paris, a red square was answered "Red", decode run-average 15.2 t/s,
prefill run-average 95 t/s.
