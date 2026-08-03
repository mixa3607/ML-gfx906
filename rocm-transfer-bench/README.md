# ROCm TransferBench (TB)
TransferBench is a utility for benchmarking simultaneous memory transfers between user-specified devices (CPUs, GPUs, and NICs).

- https://github.com/ROCm/TransferBench
- https://rocm.docs.amd.com/projects/TransferBench

## Install from APT

> **Required:** [gfx906 apt repository](../rocm/README.md#add-the-repository-ubuntu-2404) must be installed

```bash
apt-get install -y amdrocm-transferbench
```

## Build from Source

### OS Preparation

```bash
# Remove ROCm paths from env if installed
export PATH=$(echo $PATH | tr ':' '\n' | grep -v "/opt/rocm" | paste -sd:)
unset ROCM_PATH
unset ROCM_DIR
unset HIP_PATH
unset HIP_DIR

# Install Ubuntu dependencies
apt update
apt install -y \
  gfortran git ninja-build jq \
  cmake g++ pkg-config \
  xxd automake libtool \
  python3-venv python3-dev \
  libegl1-mesa-dev texinfo \
  bison flex libsqlite3-dev \
  curl make debhelper libpci3 \
  libpci-dev doxygen unzip \
  libyaml-cpp-dev libnuma-dev \
  rdma-core libibverbs-dev ibverbs-utils
```

### Build deb package

```bash
########## Clone ##########
mkdir $HOME/rocm/code/TransferBench
cd $HOME/rocm/code/TransferBench
git clone https://github.com/ROCm/TransferBench.git .

########## Configure ##########
# Packages dest dir
PACKAGES_DIR="$HOME/rocm/packages/tb"
# Path to rocm when package installed
ROCM_DEPS_DIR="/opt/rocm"
# Try search current rocm bins
ROCM_BUILD_DIR="$HOME/rocm/code/TheRock/build/dist/rocm"
if ! [ -d "$ROCM_BUILD_DIR" ]; then
  ROCM_BUILD_DIR="$ROCM_DEPS_DIR"
fi
if ! [ -d "$ROCM_BUILD_DIR" ]; then
  echo "ROCm directory not found"
fi
# Version suffix e.g. v0.1.2-<VERSION_SUFFIX>
VERSION_SUFFIX=gfx906+20260802001858

CMAKE_ARGS=(
  -DCMAKE_BUILD_TYPE="Release"
  -DROCM_PATH="${ROCM_BUILD_DIR}"
  -DROCM_MAJOR_VERSION="${ROCM_MAJOR}"
  -DHIP_PLATFORM=amd
  -DCMAKE_INSTALL_PREFIX="${ROCM_DEPS_DIR}"
  -DCPACK_PACKAGING_INSTALL_PREFIX="${ROCM_DEPS_DIR}"
  -DCPACK_PACKAGE_DIRECTORY="$PACKAGES_DIR"
  -DCMAKE_VERBOSE_MAKEFILE=ON
  -DBUILD_RELOCATABLE_PACKAGE=ON
  -DBUILD_LOCAL_GPU_TARGET_ONLY=OFF
  -DENABLE_MPI_COMM=OFF
  -DGPU_TARGETS="gfx906"
  -DTRANSFERBENCH_PACKAGE_RELEASE="${VERSION_SUFFIX}"
)
cmake -B ./build --fresh "${CMAKE_ARGS[@]}" .

########## Build ##########
# Build code
cmake --build ./build

# Build deb packages
pushd ./build; cpack -G DEB; popd
```
