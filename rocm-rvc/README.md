# ROCm Validation Suite (RVC)

## Install from APT

> **Required:** [gfx906 apt repository](../rocm/README.md#add-the-repository-ubuntu-2404) must be installed

```bash
apt-get install -y rocm-validation-suite
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
  libyaml-cpp-dev libnuma-dev
```

### Build deb package

```bash
# Clone
mkdir $HOME/rocm/code/ROCmValidationSuite
cd $HOME/rocm/code/ROCmValidationSuite
git clone https://github.com/ROCm/ROCmValidationSuite.git .

# Configure
ROCM_PATH=/opt/rocm
PACKAGES_DIR=$HOME/rocm/packages/rvc
VERSION_SUFFIX=gfx906-1

cmake -B ./build --fresh \
  -DROCM_PATH=$ROCM_PATH \
  -DCMAKE_INSTALL_PREFIX=$ROCM_PATH \
  -DCPACK_PACKAGE_DIRECTORY=$PACKAGES_DIR \
  -DCPACK_PACKAGING_INSTALL_PREFIX=$ROCM_PATH \
  -DCPACK_DEBIAN_PACKAGE_RELEASE=$VERSION_SUFFIX \
  -DRVS_BUILD_TESTS=OFF

# Build
cmake --build ./build -j 60
pushd ./build
make package
popd
```
