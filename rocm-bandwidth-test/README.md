# ROCm Bandwidth Test

ROCm Bandwidth Test measures PCIe transfer bandwidth between CPU and GPU
devices.

- https://github.com/ROCm/rocm_bandwidth_test
- https://rocm.docs.amd.com/projects/rocm_bandwidth_test/en/latest/

All packages are built for the deprecated `gfx906` GPU architecture and are not
compatible with other AMD GPUs.

## Install from APT

> **Required:** [gfx906 apt repository](../rocm/README.md#add-the-repository-ubuntu-2404) must be installed.

```bash
apt-get install -y rocm-bandwidth-test
```

The executable is installed below `/opt/rocm/extras-7`.

```bash
export PATH=/opt/rocm/extras-7/bin:$PATH
export LD_LIBRARY_PATH=/opt/rocm/extras-7/lib:$LD_LIBRARY_PATH
rocm-bandwidth-test --help
```

## Build deb package from source

The build runs in `docker buildx` on
`docker.io/mixa3607/rocm-gfx906:<ver>-complete`. It clones upstream `develop`
with its required submodules and creates a relocatable deb with CPack.

| Artifact | Script | Dockerfile |
| --- | --- | --- |
| deb | `./build-and-push.deb.sh` | `./build-deb.Dockerfile` |

### Prerequisites

- Docker with the `buildx` plugin
- Access to the ROCm base image (see the [rocm subproject](../rocm/README.md))

### Build

```bash
. preset.devel-rocm-7.14.sh
./build-and-push.deb.sh
```

The package is written to
`output/rocm<ver>/rbt-<version>-<rocm>+<arch>+<ref>/`. The script skips an
existing output directory unless `RBT_FORCE_BUILD=1` is set. Logs are written
to `logs/build_<timestamp>.log`.

### Build variables

Defaults come from [`env.sh`](./env.sh) and [`../rocm/env.sh`](../rocm/env.sh).

| Variable | Default | Description |
| --- | --- | --- |
| `RBT_VERSION` | `develop` | ROCm Bandwidth Test git tag or branch |
| `RBT_PUSH` | `0` | Set to `1` to upload the deb to the apt repository |
| `RBT_FORCE_BUILD` | *(unset)* | Set to `1` to rebuild an existing output directory |
| `ROCM_VERSION` | `7.14` | ROCm version of the base image |
| `ROCM_ARCH` | `gfx906` | Target GPU architecture |
| `ROCM_IMAGE` | `docker.io/mixa3607/rocm-gfx906` | ROCm base image name |
| `REPO_GIT_REF` | *(git tag, else short SHA)* | Build revision appended to the package release |
