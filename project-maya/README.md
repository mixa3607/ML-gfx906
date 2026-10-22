# Project Maya gfx906 (experimental)

[Project Maya](https://github.com/mw00/project-maya) for Vega20 / MI50 / MI60.
Includes the HIP `maya` (GLM) and `maya-ds4` (DeepSeek) engines, CPU GLM vision
helper and Python dashboard/API. Model weights and PyTorch conversion are not included.

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

See [RUNNING.md](RUNNING.md) for Kubernetes deployment, manual JSON, setup and
vision, or [docker-compose.example.yaml](docker-compose.example.yaml) for Docker.
