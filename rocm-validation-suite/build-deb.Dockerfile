ARG BASE_ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:latest"
ARG VERSION_SUFFIX="gfx906"
ARG RVS_REPO="https://github.com/ROCm/ROCmValidationSuite.git"
ARG RVS_BRANCH="main"

############# Build deb #############
FROM ${BASE_ROCM_IMAGE} AS build_deb
ARG RVS_REPO
ARG RVS_BRANCH

# Install Ubuntu dependencies
RUN apt-get update && apt-get install -y \
      gfortran git ninja-build jq \
      cmake g++ pkg-config \
      xxd automake libtool \
      python3-venv python3-dev \
      libegl1-mesa-dev texinfo \
      bison flex libsqlite3-dev \
      curl make debhelper libpci3 \
      libpci-dev doxygen unzip \
      libyaml-cpp-dev libnuma-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build/ROCmValidationSuite

RUN git clone --depth 1 --branch "${RVS_BRANCH}" "${RVS_REPO}" .

# Configure
ARG VERSION_SUFFIX
RUN CPACK_DEBIAN_PACKAGE_RELEASE="${VERSION_SUFFIX}" \
    cmake -B ./build --fresh \
      -DROCM_PATH="${ROCM_PATH}" \
      -DCMAKE_PREFIX_PATH="${ROCM_PATH}" \
      -DCMAKE_INSTALL_PREFIX="${ROCM_PATH}" \
      -DCPACK_PACKAGING_INSTALL_PREFIX="${ROCM_PATH}" \
      -DCPACK_PACKAGE_DIRECTORY="/dist" \
      -DRVS_BUILD_TESTS=OFF

# Build code
RUN cmake --build ./build -j$(nproc)

# Build deb packages
RUN cd ./build && make package

############# Export deb #############
FROM scratch AS final
COPY --from=build_deb /dist/* /
