# ROCm TransferBench (TB)

TransferBench is a utility for benchmarking simultaneous memory transfers between
user-specified devices (CPUs, GPUs, and NICs).

- https://github.com/ROCm/TransferBench
- https://rocm.docs.amd.com/projects/TransferBench

All deb packages are built for the deprecated `gfx906` GPU architecture and are
**not** compatible with other AMD GPUs.

## Install from APT

> **Required:** [gfx906 apt repository](../rocm/README.md#add-the-repository-ubuntu-2404) must be installed

```bash
apt-get install -y amdrocm-transferbench
```

## Build deb package from source

The build happens inside `docker buildx` on top of the ROCm base image
(`docker.io/mixa3607/rocm-gfx906:<ver>-complete`) and produces a deb package
with `cpack`.

| Artifact | Script                    | Dockerfile               |
| -------- | ------------------------- | ------------------------ |
| deb      | `./build-and-push.deb.sh` | `./build-deb.Dockerfile` |

### Prerequisites

- Docker with the `buildx` plugin
- Access to the ROCm base image (see the [rocm subproject](../rocm/README.md))
- `s3cmd` — only needed to push packages to the apt repository (not implemented yet)

### Presets

Preset files set the ROCm and TransferBench versions. Source one, then run the
build script:

```bash
. preset.tb-rocm-7.14.sh
./build-and-push.deb.sh
```

### Build variables

Defaults come from [`env.sh`](./env.sh) and [`../rocm/env.sh`](../rocm/env.sh).
Export any variable to override it.

| Variable         | Default                          | Description                                   |
| ---------------- | -------------------------------- | --------------------------------------------- |
| `TB_VERSION`     | `main`                           | TransferBench git tag/branch to build         |
| `TB_PUSH`        | `1`                              | Push deb package to the apt repository        |
| `TB_FORCE_BUILD` | *(unset)*                        | Set to `1` to rebuild even if output exists   |
| `ROCM_VERSION`   | `7.14`                           | ROCm version of the base image                |
| `ROCM_ARCH`      | `gfx906`                         | Target GPU architecture                       |
| `ROCM_IMAGE`     | `docker.io/mixa3607/rocm-gfx906` | ROCm base image name                          |
| `REPO_GIT_REF`   | *(git tag, else short SHA)*      | Build revision appended to the version suffix |

The version suffix is `<arch>+<ref>` (e.g. `gfx906+76e2dbe`), so the package is
named `amdrocm-transferbench-<ver>+gfx906.<ref>.deb`.

The build log is saved to `./logs/build_<timestamp>.log`.

### Build the deb package

```bash
. preset.tb-rocm-7.14.sh
./build-and-push.deb.sh
```

The script clones the repo inside the container (checkout `$TB_VERSION`),
configures and builds it, and writes the deb package to
`output/rocm<ver>/tb-<suffix>/`. The build is skipped if the directory already
exists, unless `TB_FORCE_BUILD=1`.

### Push

`TB_PUSH` controls pushing the package to the apt repository:

- `1` (default) — not implemented yet
- `0` — keep the package locally
