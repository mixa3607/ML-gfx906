# Build Docker Images

The image is built from pre-built TheRock `.deb` packages hosted in the APT
repository and published to Docker Hub.

## Quick Start

```bash
. preset.rocm-7.14.sh
./build-and-push.image.sh
```

## How It Works

The build script sources [`env.sh`](./env.sh) which sets sensible defaults for
all required variables. A preset file (e.g. `preset.rocm-7.14.sh`) overrides the
TheRock version. All variables can be overridden by exporting them before
running the script:

| Variable               | Default                                | Description              |
| ---------------------- | -------------------------------------- | ------------------------ |
| `ROCM_VERSION`         | `7.14`                                 | TheRock release version  |
| `ROCM_ARCH`            | `gfx906`                               | Target GPU architecture  |
| `ROCM_BASE_IMAGE`      | `docker.io/library/ubuntu:24.04`      | Base Docker image        |
| `ROCM_IMAGE`           | `docker.io/mixa3607/rocm-gfx906`      | Destination image name   |
| `ROCM_IS_RELEASE`      | `0`                                    | `1` publishes release tags; otherwise only a `-pre` tag |

The [`build-image.Dockerfile`](./build-image.Dockerfile) adds the APT repository (via
[`install-gfx906-repo.sh`](./build-context/install-gfx906-repo.sh)), then installs all
`amdrocm` packages matching the given version and architecture (`--target gfx906`).

With `ROCM_IS_RELEASE=1`, two release tags are created:

- `$ROCM_IMAGE:$ROCM_VERSION-complete-$REPO_GIT_REF` — pinned to build
  revision
- `$ROCM_IMAGE:$ROCM_VERSION-complete` — floating tag for the version

Otherwise (`ROCM_IS_RELEASE=0`, the default), only
`$ROCM_IMAGE:$ROCM_VERSION-complete-$REPO_GIT_REF-pre` is created.

The build log is saved to `./logs/build_<timestamp>.log`.

## Examples

Build for a specific TheRock version and push to a custom registry:

```bash
export ROCM_VERSION=7.14
export ROCM_IMAGE=my-registry.example.com/rocm-gfx906
./build-and-push.image.sh
```

Build for a different Ubuntu base:

```bash
export ROCM_BASE_IMAGE=docker.io/library/ubuntu:22.04
./build-and-push.image.sh
```
