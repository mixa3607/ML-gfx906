# ROCm Toolkit GFX906

Docker image based on `rocm-gfx906` with the active DEB tools from this
repository installed from the gfx906 APT repository:

- `rocm-validation-suite`
- `amdrocm7.14-transferbench`
- `amd-memory-tweak`
- `amd-tuning`

The image runs `amd-tuning-deps-installer` during its build, so UPP and Mike
Farah yq v4 are available when the container starts.

## Build

```bash
. ../rocm/preset.rocm-7.14.sh
./build-and-push.image.sh
```

The image is built from `$ROCM_IMAGE:$ROCM_VERSION-complete`. With
`ROCM_TOOLKIT_IS_RELEASE=1`, it is tagged as:

- `$ROCM_TOOLKIT_IMAGE:$ROCM_VERSION-$REPO_GIT_REF`
- `$ROCM_TOOLKIT_IMAGE:$ROCM_VERSION`

Otherwise (`ROCM_TOOLKIT_IS_RELEASE=0`, the default), only
`$ROCM_TOOLKIT_IMAGE:$ROCM_VERSION-$REPO_GIT_REF-pre` is created.

## Build variables

| Variable | Default | Description |
| --- | --- | --- |
| `ROCM_VERSION` | `7.14` | ROCm version and TransferBench package version |
| `ROCM_IMAGE` | `docker.io/mixa3607/rocm-gfx906` | ROCm base image name |
| `ROCM_TOOLKIT_IMAGE` | `docker.io/mixa3607/rocm-toolkit-gfx906` | Destination image name |
| `ROCM_TOOLKIT_IS_RELEASE` | `0` | `1` publishes release tags; otherwise only a `-pre` tag |
| `ROCM_TOOLKIT_PUSH` | `1` | Set to `0` to build without pushing |
| `ROCM_TOOLKIT_FORCE_BUILD` | *(unset)* | Set to `1` to rebuild an existing immutable tag |
