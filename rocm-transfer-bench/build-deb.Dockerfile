ARG BASE_ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:latest"
ARG ROCM_ARCH="gfx906"
ARG ROCM_VERSIOIN="7.14"
ARG VERSION_SUFFIX=$ROCM_ARCH
ARG TB_REPO="https://github.com/ROCm/TransferBench.git"
ARG TB_BRANCH="main"

############# Build deb #############
FROM ${BASE_ROCM_IMAGE} AS build_deb
ARG TB_REPO
ARG TB_BRANCH

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
      libyaml-cpp-dev libnuma-dev \
      rdma-core libibverbs-dev ibverbs-utils && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build/TransferBench

RUN git clone --depth 1 --branch "${TB_BRANCH}" "${TB_REPO}" .

# Configure
ARG ROCM_ARCH
ARG ROCM_VERSIOIN
ARG VERSION_SUFFIX
RUN cmake -B ./build --fresh \
      -DCMAKE_BUILD_TYPE="Release" \
      -DROCM_PATH="${ROCM_PATH}" \
      -DROCM_MAJOR_VERSION="${ROCM_VERSIOIN}" \
      -DHIP_PLATFORM=amd \
      -DCMAKE_INSTALL_PREFIX="${ROCM_PATH}" \
      -DCPACK_PACKAGING_INSTALL_PREFIX="${ROCM_PATH}" \
      -DCPACK_PACKAGE_DIRECTORY="/dist" \
      -DCMAKE_VERBOSE_MAKEFILE=ON \
      -DBUILD_RELOCATABLE_PACKAGE=ON \
      -DBUILD_LOCAL_GPU_TARGET_ONLY=OFF \
      -DENABLE_MPI_COMM=OFF \
      -DGPU_TARGETS="${ROCM_ARCH}" \
      -DTRANSFERBENCH_PACKAGE_RELEASE="${VERSION_SUFFIX}" \
      .

# Build code
RUN cmake --build ./build -j$(nproc)

# Build deb packages
RUN cd ./build && cpack -G DEB

############# Export deb #############
FROM scratch AS final
COPY --from=build_deb /dist/* /
