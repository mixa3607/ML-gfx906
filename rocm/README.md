# ROCm GFX906

An open software stack that includes programming models, tools, compilers,
libraries, and runtimes for AI and HPC solution development on AMD GPUs.

## Docker Image (TheRock build)

| Distro       | ROCm | Build                        | Image                                          | Status |
| ------------ | ---- | ---------------------------- | ---------------------------------------------- | ------ |
| Ubuntu 24.04 | 7.14 | 7.14.0-gfx906+20260802001858 | `docker.io/mixa3607/rocm-gfx906:7.14-complete` | ✅      |

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
| Ubuntu 24.04 | 7.14 | 7.14.0-gfx906+20260802001858 | ✅      |

### Add the repository (Ubuntu 24.04)

```bash
sudo apt-get update
sudo apt-get install ca-certificates curl -y
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://s3.arkprojects.space/apt-gfx906/ubuntu/gpg -o /etc/apt/keyrings/apt-gfx906.asc
sudo chmod a+r /etc/apt/keyrings/apt-gfx906.asc
sudo tee /etc/apt/sources.list.d/gfx906.sources <<EOF
Types: deb
URIs: https://s3.arkprojects.space/apt-gfx906/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: main
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/apt-gfx906.asc
EOF
sudo apt-get update
```

### Install ROCm

```bash
THEROCK_VERSION="7.14"
ROCM_ARCH="gfx906"
apt-get install -y amdrocm${THEROCK_VERSION}-${ROCM_ARCH}

# Optional: install ROCm Validation Suite
apt-get install -y rvc
# See ../rocm-rvc for build-from-source instructions
```

> See [BUILD-PACKAGES.md](./BUILD-PACKAGES.md) for instructions on building
> packages from source.

## Docker Image (Legacy build)

> Legacy build files deleted in `20260802001858` release

| Distro       | Version | Image                                           | Status |
| ------------ | ------- | ----------------------------------------------- | ------ |
| Ubuntu 24.04 | 6.3.3   | `docker.io/mixa3607/rocm-gfx906:6.3.3-complete` | ✅      |
| Ubuntu 24.04 | 6.4.4   | `docker.io/mixa3607/rocm-gfx906:6.4.4-complete` | ✅      |
| Ubuntu 24.04 | 7.0.0   | `docker.io/mixa3607/rocm-gfx906:7.0.0-complete` | ✅      |
| Ubuntu 24.04 | 7.0.2   | `docker.io/mixa3607/rocm-gfx906:7.0.2-complete` | ✅      |
| Ubuntu 24.04 | 7.1.0   | `docker.io/mixa3607/rocm-gfx906:7.1.0-complete` | ✅      |
| Ubuntu 24.04 | 7.1.1   | `docker.io/mixa3607/rocm-gfx906:7.1.1-complete` | ✅      |
| Ubuntu 24.04 | 7.2.0   | `docker.io/mixa3607/rocm-gfx906:7.2.0-complete` | ✅      |
| Ubuntu 24.04 | 7.2.1   | `docker.io/mixa3607/rocm-gfx906:7.2.1-complete` | ✅      |
| Ubuntu 24.04 | 7.2.2   | `docker.io/mixa3607/rocm-gfx906:7.2.2-complete` | ✅      |
| Ubuntu 24.04 | 7.2.3   | `docker.io/mixa3607/rocm-gfx906:7.2.3-complete` | ✅      |
| Ubuntu 24.04 | 7.2.4   | `docker.io/mixa3607/rocm-gfx906:7.2.4-complete` | ✅      |
