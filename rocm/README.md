# ROCm GFX906

An open software stack that includes programming models, tools, compilers,
libraries, and runtimes for AI and HPC solution development on AMD GPUs.

## Docker Image (TheRock build)

| Distro       | ROCm | Build                        | Image                                          | Status |
| ------------ | ---- | ---------------------------- | ---------------------------------------------- | ------ |
| Ubuntu 24.04 | 7.14 | 7.14.0-gfx906+20260802001858 | `docker.io/mixa3607/rocm-gfx906:7.14-complete` | ✅     |

```bash
docker pull docker.io/mixa3607/rocm-gfx906:7.14-complete
```

> See [BUILD-IMAGES.md](./BUILD-IMAGES.md) for instructions on building Docker
> images yourself.

## APT Repository (TheRock build)

> **Warning:** Do not use the official AMD repositories together with the
> gfx906 repository! This will cause multiple package conflicts.

| Distro       | ROCm | Build                        | Status |
| ------------ | ---- | ---------------------------- | ------ |
| Ubuntu 24.04 | 7.14 | 7.14.0-gfx906+20260802001858 | ✅     |

```bash
THEROCK_VERSION="7.14"
ROCM_ARCH="gfx906"
apt-get install -y amdrocm${THEROCK_VERSION}-${ROCM_ARCH}
```

> See [BUILD-PACKAGES.md](./BUILD-PACKAGES.md) for instructions on building
> packages from source.

> gfx906 has rocBLAS device libraries but no supported hipBLASLt device
> library. See [hipBLASLt and gfx906](./HIPBLASLT-GFX906.md) before using
> INT8 workloads that require `torch._int_mm`.

## Docker Image (Legacy build)

> Legacy builds (pre-TheRock) are **no longer supported** starting from the
> `20260802001858` release. If you are stuck on an old build (e.g. `6.3.3`)
> because of issues with the new TheRock builds, please
> [open an issue](https://github.com/mixa3607/ML-gfx906/issues).

| Distro       | Version | Image                                           | Status |
| ------------ | ------- | ----------------------------------------------- | ------ |
| Ubuntu 24.04 | 6.3.3   | `docker.io/mixa3607/rocm-gfx906:6.3.3-complete` | ✅     |
| Ubuntu 24.04 | 6.4.4   | `docker.io/mixa3607/rocm-gfx906:6.4.4-complete` | ✅     |
| Ubuntu 24.04 | 7.0.0   | `docker.io/mixa3607/rocm-gfx906:7.0.0-complete` | ✅     |
| Ubuntu 24.04 | 7.0.2   | `docker.io/mixa3607/rocm-gfx906:7.0.2-complete` | ✅     |
| Ubuntu 24.04 | 7.1.0   | `docker.io/mixa3607/rocm-gfx906:7.1.0-complete` | ✅     |
| Ubuntu 24.04 | 7.1.1   | `docker.io/mixa3607/rocm-gfx906:7.1.1-complete` | ✅     |
| Ubuntu 24.04 | 7.2.0   | `docker.io/mixa3607/rocm-gfx906:7.2.0-complete` | ✅     |
| Ubuntu 24.04 | 7.2.1   | `docker.io/mixa3607/rocm-gfx906:7.2.1-complete` | ✅     |
| Ubuntu 24.04 | 7.2.2   | `docker.io/mixa3607/rocm-gfx906:7.2.2-complete` | ✅     |
| Ubuntu 24.04 | 7.2.3   | `docker.io/mixa3607/rocm-gfx906:7.2.3-complete` | ✅     |
| Ubuntu 24.04 | 7.2.4   | `docker.io/mixa3607/rocm-gfx906:7.2.4-complete` | ✅     |
