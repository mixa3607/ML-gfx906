# ROCm Validation Suite (RVS)
A system validation and diagnostics tool for monitoring, stress testing, detecting, and troubleshooting issues impacting AMD GPUs in high-performance computing environments.

- https://github.com/ROCm/ROCmValidationSuite/
- https://rocm.docs.amd.com/projects/ROCmValidationSuite/en/latest/

```bash
echo 'actions:
- name: gst-581Tflops-4K4K8K-rand-bf16
  device: all
  module: gst
  log_interval: 10000
  ramp_interval: 5000
  duration: 120000
  hot_calls: 1000
  copy_matrix: false
  target_stress: 581000
  matrix_size_a: 4864
  matrix_size_b: 4096
  matrix_size_c: 8192
  matrix_init: rand
  data_type: bf16_r
  lda: 8320
  ldb: 8320
  ldc: 4992
  ldd: 4992
  transa: 1
  transb: 0
  alpha: 1
  beta: 0' > ~/gst-581Tflops-4K4K8K-rand-bf16.conf
rvs -c ~/gst-581Tflops-4K4K8K-rand-bf16.conf
```

## Install from APT

> **Required:** [gfx906 apt repository](../rocm/README.md#add-the-repository-ubuntu-2404) must be installed

```bash
apt-get install -y rocm-validation-suite
```

## Build deb package from source

The build happens inside `docker buildx` on top of the ROCm base image
(`docker.io/mixa3607/rocm-gfx906:<ver>-complete`) and produces a deb package
with `make package` (CPack).

| Artifact | Script                    | Dockerfile               |
| -------- | ------------------------- | ------------------------ |
| deb      | `./build-and-push.deb.sh` | `./build-deb.Dockerfile` |

### Prerequisites

- Docker with the `buildx` plugin
- Access to the ROCm base image (see the [rocm subproject](../rocm/README.md))

### Presets

Preset files set the ROCm and ROCmValidationSuite versions. Source one, then run
the build script:

```bash
. preset.rvs-rocm-7.14.sh
./build-and-push.deb.sh
```

### Build variables

Defaults come from [`env.sh`](./env.sh) and [`../rocm/env.sh`](../rocm/env.sh).
Export any variable to override it.

| Variable          | Default                          | Description                                   |
| ----------------- | -------------------------------- | --------------------------------------------- |
| `RVS_VERSION`     | `main`                           | ROCmValidationSuite git tag/branch            |
| `RVS_PUSH`        | `1`                              | Push deb package to the apt repository        |
| `RVS_FORCE_BUILD` | *(unset)*                        | Set to `1` to rebuild even if output exists   |
| `ROCM_VERSION`    | `7.14`                           | ROCm version of the base image                |
| `ROCM_ARCH`       | `gfx906`                         | Target GPU architecture                       |
| `ROCM_IMAGE`      | `docker.io/mixa3607/rocm-gfx906` | ROCm base image name                          |
| `REPO_GIT_REF`    | *(git tag, else short SHA)*      | Build revision appended to the version suffix |

The version suffix is `<arch>+<ref>` (e.g. `gfx906+76e2dbe`), so the package is
named `rocm-validation-suite-<ver>+gfx906.<ref>.deb`.

The build log is saved to `./logs/build_<timestamp>.log`.

### Build the deb package

```bash
. preset.rvs-rocm-7.14.sh
./build-and-push.deb.sh
```

The script clones the repo inside the container (checkout `$RVS_VERSION`),
configures and builds it, and writes the deb package to
`output/rocm<ver>/rvs-<suffix>/`. The build is skipped if the directory already
exists, unless `RVS_FORCE_BUILD=1`.
