# Strata gfx906

[Strata](https://github.com/Niko1221/Strata) inference image for AMD `gfx906`.
The engine and GPU vision encoder are built into the image. CPU vision is
included as a fallback; model weights are downloaded separately.

## Build

Requires Docker Buildx and the [ROCm base image](../rocm/README.md).
Log in to the destination registry and run from this directory:

```bash
export STRATA_IMAGE=registry.arkprojects.space/apps/strata-gfx906
export STRATA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
./build-and-push.image.sh
```

## Run

[upstream Docker documentation](https://github.com/Niko1221/Strata/blob/v0.2.3.1/docs/DOCKER.md).
