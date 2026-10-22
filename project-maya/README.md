# Project Maya gfx906 (experimental)

[Project Maya](https://github.com/mw00/project-maya) for Vega20 / MI50 / MI60.
The image includes the HIP `maya` (GLM) and `maya-ds4` (DeepSeek) engines and
the Python dashboard/API. Models are not included or downloaded at startup.
Vision helpers and PyTorch-based model conversion are not included.

## Compatibility

- Build for **gfx906**; do not use `HSA_OVERRIDE_GFX_VERSION` to spoof gfx908.
- The [gfx906 patch](build-context/patch/gfx906.patch) enables upstream's wave64
  compatibility layer, Vega20's signed dot4 and signed-zero preservation in
  INT8 latent-cache reads. Vega20 has no WMMA/MFMA; portable attention is intentional.
- The pinned llama.cpp sources are used for MMQ and native experts. No PyTorch
  or Triton is required for inference.
- Provide `/dev/kfd`, `/dev/dri`, shared memory and an adequate memlock limit.
  `HSA_FORCE_FINE_GRAIN_PCIE` is not forced.
- Budget host RAM explicitly in the model config. In particular, GLM's free-RAM
  detection can see host memory instead of a container limit; use an appropriate
  `MAYA_GLM_RAM_GB` and leave room for weights and buffers.
- gfx906 smoke/parity tests and cached DS4.1 Q8 inference were exercised during
  development. This is not a general model-quality or perplexity guarantee.

## Build from source

The Dockerfile follows the repository's llama.cpp layout: ROCm base, source
preparation, compilation and runtime. Only the two engines and their setup
metadata are copied from the build stage; test executables and build outputs
are not shipped. Python sources and the pinned llama.cpp sources remain available
for model setup, GGUF tools and upstream's source-hash check.

```bash
source ./preset.v1.1.21-rocm-10.1.sh
export MAYA_IMAGE=registry.arkprojects.space/apps/maya-gfx906
./build-and-push.image.sh
```

The script uses the shared build helpers: `check`, `build`, or check-then-build
with no argument. It pushes by default and skips existing tags. Logs go to
`logs/build_<timestamp>.log`. The Actions workflow is manual-only and does not
download model weights.

| Variable | Default | Purpose |
| --- | --- | --- |
| `MAYA_IMAGE` | `docker.io/mixa3607/maya-gfx906` | Destination image |
| `MAYA_ROCM_VERSION` | `10.1` | ROCm version |
| `MAYA_BASE_IMAGE` | `docker.io/mixa3607/rocm-gfx906:<rocm>-complete` | Base image |
| `MAYA_REPO` | `https://github.com/mw00/project-maya.git` | Source repository |
| `MAYA_BRANCH` | `v1.1.21` | Source tag/branch |
| `MAYA_COMMIT` | `451f9cb6a21ea65673bdde2e57b4a670ae2b8859` | Pinned source SHA |
| `MAYA_PATCH` | `gfx906.patch` | Patch under `build-context/patch/` |
| `MAYA_BUILD_JOBS` | `4` | Build parallelism |
| `MAYA_CMAKE_HIP_FLAGS` | empty | Additional HIP compiler flags |
| `MAYA_CCACHE_MAXSIZE` | `2G` | Persistent compiler-cache limit |
| `MAYA_PRESET_NAME` | `<source>-rocm-<rocm>` | Image tag prefix |
| `MAYA_IMAGE_TAG` | `<preset>-<repo-ref>-pre` | Primary tag override |
| `MAYA_IS_RELEASE` | `0` | `1`: omit `-pre` and also publish `<preset>` |
| `MAYA_PUSH` | `1` | `0`: load into local Docker instead of pushing |
| `MAYA_FORCE_BUILD` | `0` | Rebuild an existing tag |
| `REPO_GIT_REF` | current Git ref | Build revision suffix |

When changing the source tag, also change `MAYA_COMMIT`, or explicitly set it
to an empty string to follow the tag/branch. Incompatible patches fail the build.
`SOURCE_COMMIT` records the resolved SHA; `build-hip/MAYA-BUILD.json` records
the patched source hash, architecture and HIP flags so setup reuses the engines.

For optional max-ILP compilation, use a separate tag:

```bash
MAYA_IMAGE_TAG=v1.1.21-rocm-10.1-max-ilp \
MAYA_CMAKE_HIP_FLAGS='-mllvm -amdgpu-sched-strategy=max-ilp' \
  ./build-and-push.image.sh build
```

Experimental PR patches, cluster-specific benchmarks and their results are
kept in the `add-project-maya` branch, not in this runtime build.

## Setup and serving

Check GPU access first:

```bash
IMAGE=registry.arkprojects.space/apps/maya-gfx906:YOUR_TAG
docker run --rm --device /dev/kfd --device /dev/dri "$IMAGE" --check --gpu 0
```

Setup is explicit. This example downloads Maya-S24 (roughly 95 GB):

```bash
mkdir -p data
docker run --rm --device /dev/kfd --device /dev/dri \
  --cap-add IPC_LOCK --ulimit memlock=-1:-1 --shm-size 1g \
  -v "$PWD/data:/data" "$IMAGE" setup \
  --gpu 0 --model Maya-S24 --models-dir /data/models \
  --context 8192 --no-vision --yes --download-model \
  --env MAYA_GLM_RAM_GB=32
```

For existing GGUF shards, use `--gguf-dir /data/models/Maya-S24` instead of
`--download-model`. Setup writes packs beside the shards, so do not point it
at a read-only HF snapshot. Generated HIP configs are copied to `/data/config/`.
Model and pack paths must be the same during setup and serving.

```bash
docker run --rm --device /dev/kfd --device /dev/dri \
  --cap-add IPC_LOCK --ulimit memlock=-1:-1 --shm-size 1g \
  -p 127.0.0.1:8080:8080 -v "$PWD/data:/data" \
  -e MAYA_CONFIG=/data/config/maya-maya-s24-hip.json \
  "$IMAGE" serve
```

`serve` starts the upstream server directly, without setup or a source refresh.
It listens on `0.0.0.0:8080` inside the container; `PORT` overrides the port.
Set an API key during setup or pass `--api-key` after `serve` before exposing it
externally. Use a new image for upgrades, not the dashboard's source updater.

For multiple cards, pass `--gpus 0,1,2,3` during setup. See also
[docker-compose.example.yaml](docker-compose.example.yaml) and the upstream
[AMD notes](https://github.com/mw00/project-maya/blob/v1.1.21/docs/AMD_MAYA.md).
