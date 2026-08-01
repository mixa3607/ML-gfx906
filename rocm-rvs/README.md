# ROCm Validation Suite (RVS)
A system validation and diagnostics tool for monitoring, stress testing, detecting, and troubleshooting issues impacting AMD GPUs in high-performance computing environments

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
########## Clone ##########
mkdir $HOME/rocm/code/ROCmValidationSuite
cd $HOME/rocm/code/ROCmValidationSuite
git clone https://github.com/ROCm/ROCmValidationSuite.git .

########## Configure ##########
# Packages dest dir
PACKAGES_DIR=$HOME/rocm/packages/rvc
# Path to rocm when package installed
ROCM_DEPS_DIR=/opt/rocm
# Try search current rocm bins
ROCM_BUILD_DIR=$HOME/rocm/code/TheRock/build/dist/rocm
if ! [ -d $ROCM_BUILD_DIR ]; then
  ROCM_BUILD_DIR=$ROCM_DEPS_DIR
fi
if ! [ -d $ROCM_BUILD_DIR ]; then
  echo "ROCm directory not found"
fi
# Version suffix e.g. v0.1.2-<VERSION_SUFFIX>
VERSION_SUFFIX=gfx906-20260802001858

CPACK_DEBIAN_PACKAGE_RELEASE=$VERSION_SUFFIX \
cmake -B ./build --fresh \
  -DROCM_PATH="$ROCM_BUILD_DIR" \
  -DCMAKE_PREFIX_PATH="$ROCM_BUILD_DIR" \
  -DCMAKE_INSTALL_PREFIX="$ROCM_DEPS_DIR" \
  -DCPACK_PACKAGING_INSTALL_PREFIX="$ROCM_DEPS_DIR" \
  -DCPACK_PACKAGE_DIRECTORY="$PACKAGES_DIR" \
  -DRVS_BUILD_TESTS=OFF

########## Build ##########
# Build code
cmake --build ./build -j 60

# Build deb packages
pushd ./build; make package; popd
```
