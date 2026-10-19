# llama.cpp GFX906

LLM inference in C/C++. https://github.com/ggml-org/llama.cpp

All images are built for the deprecated `gfx906` GPU architecture and are
**not** compatible with other AMD GPUs.

## Prebuilt images

- [`docker.io/mixa3607/llama.cpp-gfx906:<ver>-rocm-10.1`](https://hub.docker.com/r/mixa3607/llama.cpp-gfx906/tags?name=rocm-10.1)\*
- [`docker.io/mixa3607/llama.cpp-gfx906:<ver>-rocm-10.1-mxxm`](https://hub.docker.com/r/mixa3607/llama.cpp-gfx906/tags?name=rocm-10.1-mxxm)\*

> \* have daily builds. See last tag on Docker Hub.

## Server profiles

See the [server profiles documentation](./build-context/extra/server-profiles/README.md)
for optional YAML/JSON model presets.

## Benchmark profiles

See the [benchmark profiles documentation](./build-context/extra/bench-profiles/README.md)
for YAML/JSON benchmark matrices and shell command templates.

## Benchmark results

See the [benchmark results documentation](./build-context/extra/bench-results/README.md)
for converting llama-bench JSONL output into YAML, JSON, or Markdown tables.

## Router child wrapper

See the [child wrapper](./build-context/extra/child-wrapper/README.md) for
intercepting router child launches without modifying llama.cpp. Set
`M36_LLAMA_CHILD_WRAPPER` to an executable script's absolute container path;
`entrypoint.sh` enables the preload hook automatically.

## Build from source

The build happens inside `docker buildx` on top of the ROCm base image
(`docker.io/mixa3607/rocm-gfx906:<rocm>-complete`) and produces the llama.cpp image.

| Artifact | Script                      | Dockerfile                 |
| -------- | --------------------------- | -------------------------- |
| Image    | `./build-and-push.image.sh` | `./build-image.Dockerfile` |

### Build variables

Defaults are defined in [`build-and-push.image.sh`](./build-and-push.image.sh).
Export any variable to override it.

| Variable                | Default                                     | Description                                        |
| ----------------------- | ------------------------------------------- | -------------------------------------------------- |
| `LLAMA_IMAGE`           | `docker.io/mixa3607/llama.cpp-gfx906`       | Destination image name                             |
| `LLAMA_ROCM_VERSION`    | `7.14`                                      | ROCm version of the base image                     |
| `LLAMA_REPO`            | `https://github.com/ggml-org/llama.cpp.git` | llama.cpp git repository                           |
| `LLAMA_BRANCH`          | `master`                                    | llama.cpp git tag/branch to build                  |
| `LLAMA_COMMIT`          | _(empty)_                                   | Pin a specific commit (on top of the branch)       |
| `LLAMA_CMAKE_HIP_FLAGS` | _(empty)_                                   | Extra HIP flags appended to the build              |
| `LLAMA_CCACHE_MAXSIZE`  | `2G`                                        | ccache size limit; ccache is mounted across builds |
| `LLAMA_IS_RELEASE`      | `0`                                         | `1` — full tags; otherwise `-pre` tag only         |
| `LLAMA_PUSH`            | `1`                                         | Push the image to the registry                     |
| `LLAMA_FORCE_BUILD`     | _(unset)_                                   | Set to `1` to rebuild even if the tag exists       |
| `ROCM_ARCH`             | `gfx906`                                    | Target GPU architecture                            |
| `ROCM_IMAGE`            | `docker.io/mixa3607/rocm-gfx906`            | ROCm base image name                               |
| `REPO_GIT_REF`          | _(git tag, else short SHA)_                 | Build revision appended to the tag                 |

### Build the image

```bash
. preset.v0.6.0-rocm-7.14-ggml.sh
export LLAMA_IMAGE=registry.example.com/apps/llama.cpp-gfx906
export ROCM_IMAGE=registry.example.com/apps/rocm-gfx906
export LLAMA_ROCM_VERSION="7.14"
export LLAMA_REPO="https://github.com/ggml-org/llama.cpp.git"
export LLAMA_BRANCH='v0.6.0'
export LLAMA_PRESET_NAME="${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}"
export LLAMA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
./build-and-push.image.sh
```

The build log is saved to `./logs/build_<timestamp>.log`.
