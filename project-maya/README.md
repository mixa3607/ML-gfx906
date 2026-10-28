# Project Maya gfx906 (experimental)

[Project Maya](https://github.com/mw00/project-maya) for Vega20 / MI50 / MI60.
The image contains the HIP `maya` (GLM / CYBER-FROST), `maya-ds4` (DeepSeek), and
`maya-mm3` (MiniMax, v1.1.35 preset) engines, the
CPU GLM vision helper, upstream tools, Python dependencies and the `hf` CLI.
Model weights and PyTorch conversion are not included.

## Compatibility

- Use **gfx906**, without `HSA_OVERRIDE_GFX_VERSION`. The
  [v1.1.32 patch](build-context/patch/v1.1.32.patch) only preserves signed zero
  in INT8 latent-cache reads on Vega20.
- Provide `/dev/kfd`, `/dev/dri`, shared memory and an adequate memlock limit.
- Set `MAYA_GLM_RAM_GB` explicitly for GLM: the engine's free-RAM detection can
  see host memory instead of the container limit. Leave room for weights and
  buffers.

## Images

The build example below uses a registry of your choice. The
[Actions workflow](../.github/workflows/maya-build.yaml) publishes to the
registry selected by the workflow secrets.

## Build

Requires Docker Buildx and the [ROCm base image](../rocm/README.md).
Log in to the destination registry and run from this directory:

```bash
source ./preset.v1.1.35-rocm-10.1.sh
export MAYA_IMAGE=registry.example.com/apps/maya-gfx906
./build-and-push.image.sh
```

For local test builds, `../.build/.env-local.sh` sets `MAYA_IMAGE` to the
private test registry.

The example enables the tested max-ILP scheduling flag. The defaults use `main`
and `empty.patch` (no changes to upstream); gfx906 needs a matching patch selected
explicitly, as above.

The script builds and pushes, skipping existing tags; `MAYA_FORCE_BUILD=1`
forces a rebuild. The build log is saved to `./logs/build_<timestamp>.log`.

Defaults are defined in [`build-and-push.image.sh`](build-and-push.image.sh).
Export a variable to override it.

| Variable               | Default                                    | Description                                             |
| ---------------------- | ------------------------------------------ | ------------------------------------------------------- |
| `MAYA_IMAGE`           | `docker.io/mixa3607/maya-gfx906`           | Destination image name                                  |
| `MAYA_ROCM_VERSION`    | `10.1`                                     | ROCm version of the base image                          |
| `MAYA_REPO`            | `https://github.com/mw00/project-maya.git` | Project Maya git repository                             |
| `MAYA_BRANCH`          | `main`                                     | Project Maya tag/branch to build                        |
| `MAYA_COMMIT`          | _(empty)_                                  | Pin a specific commit (on top of the branch)            |
| `MAYA_PATCH`           | `empty.patch`                              | Patch file or directory under `build-context/patch/`    |
| `MAYA_CMAKE_HIP_FLAGS` | _(empty)_                                  | Extra HIP flags appended to the engine build            |
| `MAYA_BUILD_JOBS`      | `nproc`                                    | Parallel compile jobs                                   |
| `MAYA_CCACHE_MAXSIZE`  | `2G`                                       | ccache size limit; ccache is mounted across builds      |
| `MAYA_IS_RELEASE`      | `0`                                        | `1` publishes release tags; otherwise only a `-pre` tag |
| `MAYA_PUSH`            | `1`                                        | Push the image to the registry                          |
| `MAYA_FORCE_BUILD`     | _(unset)_                                  | Set to `1` to rebuild even if the tag exists            |
| `ROCM_ARCH`            | `gfx906`                                   | Target GPU architecture                                 |
| `ROCM_IMAGE`           | `docker.io/mixa3607/rocm-gfx906`           | ROCm base image name                                    |
| `REPO_GIT_REF`         | _(git tag, else short SHA)_                | Build revision appended to the tag                      |

## Run

See [RUNNING.md](RUNNING.md) for preparation, configuration and Kubernetes
deployment, or [docker-compose.example.yaml](docker-compose.example.yaml) for
Docker.

The v1.1.35 preset pins upstream `e16dec85abf8801a4cfc086ee4814071a3ff54a2`
and reuses the v1.1.32 signed-zero patch. Per-model offline preparation scripts
and configs for GLM-S24, MiniMax-XS and CYBER-FROST are described in
[smoke-v1.1.35/README.md](smoke-v1.1.35/README.md).
