# Project Maya gfx906 (experimental)

[Project Maya](https://github.com/mw00/project-maya) for Vega20 / MI50 / MI60.
Includes the HIP `maya` (GLM) and `maya-ds4` (DeepSeek) engines and Python
dashboard/API. Models, vision helpers and PyTorch conversion are not included.

## Compatibility

- Use **gfx906**, without `HSA_OVERRIDE_GFX_VERSION`. The
  [patch](build-context/patch/gfx906.patch) enables wave64, signed dot4 and
  signed-zero preservation in INT8 latent-cache reads.
- Provide `/dev/kfd`, `/dev/dri`, shared memory and an adequate memlock limit.
- Set `MAYA_GLM_RAM_GB` explicitly: GLM's free-RAM detection can see host memory
  instead of the container limit. Leave room for weights and buffers.

## Build

Requires Docker Buildx and the [ROCm base image](../rocm/README.md).
Log in to the destination registry and run from this directory:

```bash
source ./preset.v1.1.24-rocm-10.1.sh
export MAYA_IMAGE=registry.arkprojects.space/apps/maya-gfx906
./build-and-push.image.sh
```

The script builds and pushes, skipping existing tags; `MAYA_FORCE_BUILD=1`
forces a rebuild. Defaults are in the [build script](build-and-push.image.sh).
`MAYA_BUILD_JOBS` limits parallelism (otherwise `nproc`);
`MAYA_CMAKE_HIP_FLAGS` sets extra compiler flags.

When using a versioned preset, change or unset its `MAYA_COMMIT` when changing
the source tag. Without a commit override, the build follows the tag/branch.

The [Actions workflow](../.github/workflows/maya-build.yaml) builds the latest
upstream release unless `maya_tag` is specified.

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
