# Build Packages from Source

## OS Preparation

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

## Build TheRock

```bash
########## Clone ##########
mkdir $HOME/rocm/code/TheRock
cd $HOME/rocm/code/TheRock
git clone https://github.com/ROCm/TheRock.git .

########## Install deps ##########
# Install ccache
./dockerfiles/install_ccache.sh 4.12.2

# Install a patched patchelf from source. For details see
# https://github.com/ROCm/TheRock/blob/main/docs/environment_setup_guide.md#patchelf
env INSTALL_PREFIX=/usr/local ./dockerfiles/install_pinned_patchelf.sh

# Init python virtual environment and install python dependencies
if ! [ -d .venv ]; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
fi
source .venv/bin/activate

# Download submodules and apply patches
python3 ./build_tools/fetch_sources.py

########## Configure ##########
PACKAGES_DIR=$HOME/rocm/packages/therock
VERSION_SUFFIX=gfx906+20260802001858

eval "$(./build_tools/setup_ccache.py)"
CMAKE_ARGS=(
  # ccache
  -DCMAKE_C_COMPILER_LAUNCHER=ccache
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
  # set arch
  -DTHEROCK_AMDGPU_FAMILIES=gfx906
  # disable not supported
  -DTHEROCK_ENABLE_ROCWMMA=OFF
  -DTHEROCK_ENABLE_HIPBLASLTPROVIDER=OFF
  # datacenter features
  -DTHEROCK_ENABLE_DC_TOOLS=OFF
  -DTHEROCK_ENABLE_ROCSHMEM=OFF
  # misc
  -DTHEROCK_ENABLE_ROCJITSU=OFF
  -DTHEROCK_ENABLE_FFTW3=OFF
  -DTHEROCK_ENABLE_HIPFILE=OFF
  -DTHEROCK_ENABLE_MEDIA_LIBS=OFF
  # disable tests
  #-DTHEROCK_BUILD_TESTING=OFF
)
cmake -B ./build -G Ninja --fresh "${CMAKE_ARGS[@]}" .

########## Build ##########
# Build code (10_000_000 years)
cmake --build ./build

# Build deb packages
./build_tools/packaging/linux/build_package.py \
   --artifacts-dir ./build/artifacts \
   --target gfx906 \
   --dest-dir $PACKAGES_DIR \
   --rocm-version "$(cat version.json | jq '."rocm-version"' -r)" \
   --version-suffix $VERSION_SUFFIX \
   --pkg-type deb
```

> Parallelism control https://github.com/ROCm/TheRock/blob/main/docs/environment_setup_guide.md#resource-utilization
