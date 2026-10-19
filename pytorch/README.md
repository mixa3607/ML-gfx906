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
| 2.14.1 | 10.1 | `docker.io/mixa3607/pytorch-gfx906:v2.14.1-rocm-10.1` |
| 2.14.1 | 10.0 | `docker.io/mixa3607/pytorch-gfx906:v2.14.1-rocm-10.0` |
| 2.14.1 | 7.14 | `docker.io/mixa3607/pytorch-gfx906:v2.14.1-rocm-7.14` |
| 2.13.0 | 7.14 | `docker.io/mixa3607/pytorch-gfx906:v2.13.0-rocm-7.14` |

The image is based on `docker.io/mixa3607/rocm-gfx906:<ver>-complete` and has
`torch`, `torchvision` and `torchaudio` pre-installed.

### Wheels

| Torch  | ROCm | URL                                                                                           |
| ------ | ---- | --------------------------------------------------------------------------------------------- |
| 2.14.1 | 10.1 | https://s3.arkprojects.space/py-gfx906/rocm10.1/torch-v2.14.1+gfx906.20261018172427/index.txt |
| 2.14.1 | 10.0 | https://s3.arkprojects.space/py-gfx906/rocm10.0/torch-v2.14.1+gfx906.20261018172427/index.txt |
| 2.14.1 | 7.14 | https://s3.arkprojects.space/py-gfx906/rocm7.14/torch-v2.14.1+gfx906.20261018172427/index.txt |
| 2.13.0 | 7.14 | https://s3.arkprojects.space/py-gfx906/rocm7.14/torch-v2.13.0+gfx906.20260802001858/index.txt |

Wheels are built for **Python 3.12** (`cp312`) on `linux_x86_64`.

## Usage

### Install wheels in a virtual environment

Download the wheels directly and install them:

```bash
python3 -m venv .venv
source .venv/bin/activate
PACKAGES_ROOT=https://s3.arkprojects.space/py-gfx906/rocm10.1/torch-v2.14.1+gfx906.20261018172427
curl -O $PACKAGES_ROOT/index.txt
# install every file listed in index.txt
while read -r f; do
  curl -O "$PACKAGES_ROOT/$f"
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
   docker.io/mixa3607/pytorch-gfx906:v2.14.1-rocm-10.1
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
. preset.torch-2.14.1-rocm-10.1.sh
./build-and-push.whl.sh
```

### Build variables

Defaults are defined in [`build-and-push.whl.sh`](./build-and-push.whl.sh) and
[`build-and-push.image.sh`](./build-and-push.image.sh). Export any variable to override it.

| Variable                | Default                             | Description                                                   |
| ----------------------- | ----------------------------------- | ------------------------------------------------------------- |
| `TORCH_ROCM_VERSION`    | `7.14`                              | ROCm version of the base image                                |
| `TORCH_VERSION`         | `v2.14.0`                           | PyTorch git tag/branch to build                               |
| `TORCH_IMAGE`           | `docker.io/mixa3607/pytorch-gfx906` | Destination image name                                        |
| `TORCH_IS_RELEASE`      | `0`                                 | `1` publishes image release tags; otherwise only a `-pre` tag |
| `TORCH_PUSH`            | `0` (whl), `1` (image)              | Push wheels to S3 (`whl`) / image to registry (`image`)       |
| `TORCH_PACKAGES_SOURCE` | `fetch`                             | `fetch` — download wheels from S3; `context` — use local      |
| `ROCM_ARCH`             | `gfx906`                            | Target GPU architecture                                       |
| `ROCM_IMAGE`            | `docker.io/mixa3607/rocm-gfx906`    | ROCm base image name                                          |
| `TORCH_MAX_JOBS`        | _(auto: nproc)_                     | Parallel build jobs for PyTorch                               |
| `TORCH_VISION_VERSION`  | _(PyTorch CI pin)_                  | Override torchvision git tag/branch                           |
| `TORCH_FORCE_BUILD`     | _(unset)_                           | Set to `1` to rebuild even if the artifact already exists     |
| `REPO_GIT_REF`          | _(git tag, else short SHA)_         | Build revision appended to the version suffix                 |

The version suffix is `<arch>.<ref>` (e.g. `gfx906.76e2dbe`), so wheels are
named `torch-<ver>+gfx906.<ref>-cp312-cp312-linux_x86_64.whl`.

The build log is saved to `./logs/build_<timestamp>.log`.

### Build wheels

```bash
. preset.torch-2.14.1-rocm-10.1.sh
./build-and-push.whl.sh
```

Wheels are written to `output/rocm<ver>/torch-<ver>+<suffix>/`. The wheel script
supports the [common build commands](../.build/README.md):

- `check`: print `true` if a build is needed, or `false` to skip.
- `build`: build and optionally publish without checking existing wheels.
- No arguments: check, then build or skip.

`torchvision` and `torchaudio` are pinned to the commit referenced in the PyTorch
`ci_commit_pins` by default; override with `TORCH_VISION_VERSION` (audio is
always pinned).

### Build the image

```bash
. preset.torch-2.14.1-rocm-10.1.sh
./build-and-push.image.sh
```

With `TORCH_IS_RELEASE=1`, two image tags are created:

- `$TORCH_IMAGE:$TORCH_VERSION-rocm-$TORCH_ROCM_VERSION-$REPO_GIT_REF` — pinned
  to the build revision
- `$TORCH_IMAGE:$TORCH_VERSION-rocm-$TORCH_ROCM_VERSION` — floating tag

Otherwise (`TORCH_IS_RELEASE=0`, the default), only
`$TORCH_IMAGE:$TORCH_VERSION-rocm-$TORCH_ROCM_VERSION-$REPO_GIT_REF-pre` is
created.

The image script needs wheels:

- `TORCH_PACKAGES_SOURCE=fetch` (default) — downloads them from the S3 index
- `TORCH_PACKAGES_SOURCE=context` — uses wheels already built in
  `output/rocm<ver>/torch-<ver>+<suffix>/` (run the whl script first)

The build is skipped if the pinned tag is already in the registry, unless
`TORCH_FORCE_BUILD=1`.

### Push

Both scripts respect `TORCH_PUSH`:

- `whl`: uploads the output directory to `TORCH_PACKAGES_S3` with public ACL
- `image`: adds `--push` to the buildx build

Set `TORCH_PUSH=0` to disable uploads (images are not automatically loaded into Docker).

### Custom registry / local overrides

Example:

```bash
export TORCH_ROCM_VERSION=10.1
export TORCH_VERSION=v2.14.1
export TORCH_IMAGE=registry.example.com/apps/pytorch-gfx906
export ROCM_IMAGE=registry.example.com/apps/rocm-gfx906
export TORCH_MAX_JOBS=32
./build-and-push.whl.sh
```

See [`../.build/.env-local.sh`](../.build/.env-local.sh) for a ready-made local override file.

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
