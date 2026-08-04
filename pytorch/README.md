# PyTorch GFX906

Tensors and Dynamic neural networks in Python with strong GPU acceleration.

Packages:

- torch
- torchvision
- torchaudio

All wheels and images are built for the deprecated `gfx906` GPU architecture and
are **not** compatible with other AMD GPUs.

## Prebuilt artifacts

### Docker image

| Torch  | ROCm | Image                                                 |
| ------ | ---- | ----------------------------------------------------- |
| 2.13.0 | 7.14 | `docker.io/mixa3607/pytorch-gfx906:v2.13.0-rocm-7.14` |

The image is based on `docker.io/mixa3607/rocm-gfx906:<ver>-complete` and has
`torch`, `torchvision` and `torchaudio` pre-installed.

### Wheels

| Torch  | ROCm | URL                                                                                    |
| ------ | ---- | -------------------------------------------------------------------------------------- |
| 2.13.0 | 7.14 | https://s3.arkprojects.space/py-gfx906/rocm7.14/torch-v2.13.0+gfx906.76e2dbe/index.txt |

Wheels are built for **Python 3.12** (`cp312`) on `linux_x86_64`.

## Usage

### Install wheels in a virtual environment

Download the wheels directly and install them:

```bash
python3 -m venv .venv
source .venv/bin/activate
curl -O https://s3.arkprojects.space/py-gfx906/rocm7.14/torch-v2.13.0+gfx906.76e2dbe/index.txt
# install every file listed in index.txt
while read -r f; do
  curl -O "https://s3.arkprojects.space/py-gfx906/rocm7.14/torch-v2.13.0+gfx906.76e2dbe/$f"
done < index.txt
pip install *.whl
```

The wheels require the patched ROCm stack for gfx906 installed on the host. See
the [rocm subproject](../rocm/README.md).

### Run the Docker image

```bash
docker run --rm -it \
  --device=/dev/kfd --device=/dev/dri \
  --group-add video --group-add render \
  docker.io/mixa3607/pytorch-gfx906:v2.13.0-rocm-7.14
```

Sanity check:

```bash
python3 -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

## Build from source

The build happens inside `docker buildx` on top of the ROCm base image
(`docker.io/mixa3607/rocm-gfx906:<ver>-complete`). Two artifacts can be
produced, each with its own script and Dockerfile:

| Artifact | Script                      | Dockerfile                 |
| -------- | --------------------------- | -------------------------- |
| Wheels   | `./build-and-push.whl.sh`   | `./build-whl.Dockerfile`   |
| Image    | `./build-and-push.image.sh` | `./build-image.Dockerfile` |

### Prerequisites

- Docker with the `buildx` plugin
- Access to the ROCm base image (see the [rocm subproject](../rocm/README.md))
- `s3cmd` — only needed to push wheels to S3 (`TORCH_PUSH=1`)

### Presets

Preset files set the ROCm and PyTorch versions. Source one, then run a build
script:

```bash
. preset.torch-2.13.0-rocm-7.14.sh
./build-and-push.whl.sh
```

### Build variables

Defaults come from [`env.sh`](./env.sh) (pytorch) and
[`../rocm/env.sh`](../rocm/env.sh). Export any variable to override it.

| Variable                | Default                             | Description                                               |
| ----------------------- | ----------------------------------- | --------------------------------------------------------- |
| `TORCH_ROCM_VERSION`    | `7.14`                              | ROCm version of the base image                            |
| `TORCH_VERSION`         | `v2.13.0`                           | PyTorch git tag/branch to build                           |
| `TORCH_IMAGE`           | `docker.io/mixa3607/pytorch-gfx906` | Destination image name                                    |
| `TORCH_PUSH`            | `1`                                 | Push wheels to S3 (`whl`) / image to registry (`image`)   |
| `TORCH_PACKAGES_SOURCE` | `fetch`                             | `fetch` — download wheels from S3; `context` — use local  |
| `ROCM_ARCH`             | `gfx906`                            | Target GPU architecture                                   |
| `ROCM_IMAGE`            | `docker.io/mixa3607/rocm-gfx906`    | ROCm base image name                                      |
| `TORCH_MAX_JOBS`        | *(auto: nproc)*                     | Parallel build jobs for PyTorch                           |
| `TORCH_VISION_VERSION`  | *(PyTorch CI pin)*                  | Override torchvision git tag/branch                       |
| `TORCH_FORCE_BUILD`     | *(unset)*                           | Set to `1` to rebuild even if the artifact already exists |
| `REPO_GIT_REF`          | *(git tag, else short SHA)*         | Build revision appended to the version suffix             |

The version suffix is `<arch>.<ref>` (e.g. `gfx906.76e2dbe`), so wheels are
named `torch-<ver>+gfx906.<ref>-cp312-cp312-linux_x86_64.whl`.

The build log is saved to `./logs/build_<timestamp>.log`.

### Build wheels

```bash
. preset.torch-2.13.0-rocm-7.14.sh
./build-and-push.whl.sh
```

Wheels are written to `output/rocm<ver>/torch-<ver>+<suffix>/`. The script skips
the build if the directory already exists, unless `TORCH_FORCE_BUILD=1`.

`torchvision` and `torchaudio` are pinned to the commit referenced in the PyTorch
`ci_commit_pins` by default; override with `TORCH_VISION_VERSION` (audio is
always pinned).

### Build the image

```bash
. preset.torch-2.13.0-rocm-7.14.sh
./build-and-push.image.sh
```

Two tags are created:

- `$TORCH_IMAGE:$TORCH_VERSION-rocm-$TORCH_ROCM_VERSION-$REPO_GIT_REF` — pinned
  to the build revision
- `$TORCH_IMAGE:$TORCH_VERSION-rocm-$TORCH_ROCM_VERSION` — floating tag

The image script needs wheels:

- `TORCH_PACKAGES_SOURCE=fetch` (default) — downloads them from the S3 index
- `TORCH_PACKAGES_SOURCE=context` — uses wheels already built in
  `output/rocm<ver>/torch-<ver>+<suffix>/` (run the whl script first)

The build is skipped if the pinned tag is already in the registry, unless
`TORCH_FORCE_BUILD=1`.

### Push

Both scripts respect `TORCH_PUSH`:

- `whl`: creates a venv, installs `s3cmd`, writes `index.txt` and uploads the
  whole `output/rocm<ver>/` directory to `s3://py-gfx906/` with public ACL
- `image`: adds `--push` to the buildx build

Set `TORCH_PUSH=0` to keep the artifacts locally.

### Custom registry / local overrides

Example:

```bash
export TORCH_ROCM_VERSION=7.14
export TORCH_VERSION=v2.13.0
export TORCH_IMAGE=registry.example.com/apps/pytorch-gfx906
export ROCM_IMAGE=registry.example.com/apps/rocm-gfx906
export TORCH_MAX_JOBS=32
./build-and-push.whl.sh
```

See [`../.env-local.sh`](../.env-local.sh) for a ready-made local override file.

## Docs

https://arkprojects.space/wiki/AMD_GFX906

## Prebuilt images (Legacy builds)

- [`docker.io/mixa3607/pytorch-gfx906:v2.7.1-rocm-6.4.4`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.7.1-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.8.0-rocm-6.4.4`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.8.0-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.9.0-rocm-6.4.4`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.9.0-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.9.0-rocm-7.0.2`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.10.0-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.10.0-rocm-7.2.0`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.11.0-rocm-6.3.3`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.11.0-rocm-7.2.0`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
- [`docker.io/mixa3607/pytorch-gfx906:v2.11.0-rocm-7.2.1`](https://hub.docker.com/r/mixa3607/pytorch-gfx906/tags)
