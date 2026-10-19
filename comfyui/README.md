# ComfyUI GFX906

The most powerful and modular diffusion model GUI, API and backend with a
graph/nodes interface. https://github.com/Comfy-Org/ComfyUI

All images are built for the deprecated `gfx906` GPU architecture and are
**not** compatible with other AMD GPUs.

## Prebuilt images

- [`docker.io/mixa3607/comfyui-gfx906:<ver>-rocm-10.1`](https://hub.docker.com/r/mixa3607/comfyui-gfx906/tags?name=rocm-10.1)\*

> \* have daily builds. See last tag on Docker Hub.

## Run

### ROCm 7.14+ compatibility

**ComfyUI v0.34.0 and newer require `--disable-dynamic-vram` on gfx906 with
ROCm 7.14 or newer.**

### Docker

The image needs ROCm device access. Example:

```bash
docker run --rm \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  -p 8188:8188 \
  -e PERSISTENCE_PATH=/data \
  -v $(pwd)/data:/data \
   docker.io/mixa3607/comfyui-gfx906:latest-rocm-10.1 \
  --disable-dynamic-vram
```

Environment variables:

| Variable                              | Description                                                                                                                        |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `PERSISTENCE_PATH`                    | Copy `models`, `custom_nodes`, `input`, `output` there; use it as `--base-directory` and store the SQLite DB                       |
| `VENV_NAME`                           | Create/activate a virtual environment (with `--system-site-packages`) at `/data/<venv>` (with persistence) or `/comfyui/<venv>`    |
| `BOOTSTRAP_ONLY`                      | Set to `1` to only prepare persistence/venv and exit without starting ComfyUI                                                      |
| `PYTORCH_TUNABLEOP_ENABLED`           | Default `1`: use saved TunableOp algorithm selections when available                                                               |
| `PYTORCH_TUNABLEOP_TUNING`            | Default `0`: do not search for new algorithms; set to `1` for a tuning session                                                     |
| `PYTORCH_TUNABLEOP_HIPBLASLT_ENABLED` | Default `0`: exclude hipBLASLt candidates, whose installed kernels do not support gfx906                                           |
| `PYTORCH_TUNABLEOP_FILENAME`          | Default `/data/tunableop_results.csv`: base path for persistent tuning results; PyTorch adds the visible GPU ordinal before `.csv` |

Behavior:

- Always runs with `--enable-manager`
- With `PERSISTENCE_PATH` set, data and the SQLite database
  (`sqlite:///<PERSISTENCE_PATH>/database/comfyui.db`) are persisted to the
  mounted volume
- Additional CLI args can be appended to the `docker run` command

Also see https://github.com/hartmark/sd-rocm/blob/main/docker-compose.yml

### Kubernetes

Helm chart and samples: [mixa3607 charts](https://github.com/mixa3607/charts)

## TunableOp performance tuning

PyTorch TunableOp benchmarks alternative rocBLAS algorithms for GEMM/BMM
(matrix multiplication) and records the fastest valid selection for each
operation signature. It can **reduce sampling time by 30% or more** on
matrix-heavy workloads: a tested MI50 Anima workflow went from approximately
150s to 100s with the same model and 40 sampling steps. This is a measured
example, not a guaranteed improvement for every model or workflow. Algorithm
changes can introduce small floating-point differences; results need not be
bit-identical.

### Generate and accumulate results

The image does not bundle a pre-tuned CSV. Mount a writable persistent `/data`
volume and temporarily override `PYTORCH_TUNABLEOP_TUNING=1`:

```bash
docker run --rm \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  -p 8188:8188 \
  -e PERSISTENCE_PATH=/data \
  -e PYTORCH_TUNABLEOP_TUNING=1 \
  -v $(pwd)/data:/data \
   docker.io/mixa3607/comfyui-gfx906:latest-rocm-10.1 \
  --disable-dynamic-vram
```

Run representative workflows with the models, resolutions and batch sizes you
intend to use. New signatures trigger an algorithm search, so initial runs can
be much slower than normal inference. Existing signatures from a successfully
loaded CSV reuse their saved selections instead of being tuned again. Other
sizes, strides or dtypes may produce new signatures and extend the results.

After the workflows finish, shut down ComfyUI normally so results are written;
do not force-kill the process. For visible GPU 0, the output is
`/data/tunableop_results0.csv` (`./data/tunableop_results0.csv` on the host in
the example above). Keep the environment variable **without** the GPU suffix:
`PYTORCH_TUNABLEOP_FILENAME=/data/tunableop_results.csv`. The ordinal is the
process-visible device index, not necessarily the physical GPU number.

## Build from source

The build happens inside `docker buildx` on top of the PyTorch base image
(`docker.io/mixa3607/pytorch-gfx906:<torch>-rocm-<rocm>`) and produces the
ComfyUI image.

| Artifact | Script                      | Dockerfile                 |
| -------- | --------------------------- | -------------------------- |
| Image    | `./build-and-push.image.sh` | `./build-image.Dockerfile` |

```bash
export COMFYUI_ROCM_VERSION=10.1
export COMFYUI_PYTORCH_VERSION=2.14.1
export COMFYUI_BRANCH=v0.42.1
export COMFYUI_IMAGE=registry.example.com/apps/comfyui-gfx906
export COMFYUI_TORCH_IMAGE=registry.example.com/apps/pytorch-gfx906
./build-and-push.image.sh
```

### Build variables

Defaults are defined in [`build-and-push.image.sh`](./build-and-push.image.sh). Export
any variable to override it.

| Variable                  | Default                                    | Description                                                   |
| ------------------------- | ------------------------------------------ | ------------------------------------------------------------- |
| `COMFYUI_IMAGE`           | `docker.io/mixa3607/comfyui-gfx906`        | Destination image name                                        |
| `COMFYUI_TORCH_IMAGE`     | `docker.io/mixa3607/pytorch-gfx906`        | PyTorch base image name                                       |
| `COMFYUI_ROCM_VERSION`    | `6.3.3`                                    | ROCm version of the base image                                |
| `COMFYUI_PYTORCH_VERSION` | `2.7.1`                                    | PyTorch version of the base image                             |
| `COMFYUI_REPO`            | `https://github.com/Comfy-Org/ComfyUI.git` | ComfyUI git repository                                        |
| `COMFYUI_BRANCH`          | `master`                                   | ComfyUI git tag/branch to build                               |
| `COMFYUI_COMMIT`          | _(empty)_                                  | Pin a specific commit (on top of the branch)                  |
| `COMFYUI_IS_RELEASE`      | `0`                                        | `1` publishes image release tags; otherwise only a `-pre` tag |
| `COMFYUI_PUSH`            | `1`                                        | Push the image to the registry                                |
| `COMFYUI_FORCE_BUILD`     | _(unset)_                                  | Set to `1` to rebuild even if the tag exists                  |
| `REPO_GIT_REF`            | _(git tag, else short SHA)_                | Build revision appended to the tag                            |

## Prebuilt images (legacy builds)

- [`docker.io/mixa3607/comfyui-gfx906:<ver>-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/comfyui-gfx906/tags?name=rocm-6.3.3)
- [`docker.io/mixa3607/comfyui-gfx906:<ver>-rocm-7.2.1`](https://hub.docker.com/r/mixa3607/comfyui-gfx906/tags?name=rocm-7.2.1)
