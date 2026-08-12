ARG BASE_ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:latest"
ARG ROCM_ARCH="gfx906"
ARG ROCM_VERSION="7.14"
ARG VERSION_SUFFIX="gfx906"
ARG RBT_REPO="https://github.com/ROCm/rocm_bandwidth_test.git"
ARG RBT_BRANCH="develop"

############# Build deb #############
FROM ${BASE_ROCM_IMAGE} AS build_deb
ARG ROCM_ARCH
ARG ROCM_VERSION
ARG VERSION_SUFFIX
ARG RBT_REPO
ARG RBT_BRANCH

RUN apt-get update && apt-get install -y \
      cmake g++ git make pkg-config \
      curl libcurl4-openssl-dev \
      libdrm-dev libnuma-dev libpci-dev libyaml-cpp-dev \
      doxygen patchelf dpkg-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build/rocm_bandwidth_test

RUN git clone --depth 1 --recurse-submodules --jobs 8 \
      --branch "${RBT_BRANCH}" "${RBT_REPO}" .

RUN CPACK_DEBIAN_PACKAGE_RELEASE="${VERSION_SUFFIX}" \
    CPACK_RPM_PACKAGE_RELEASE="${VERSION_SUFFIX}" \
    cmake -B ./build --fresh \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH="${ROCM_PATH}" \
      -DROCM_PATH="${ROCM_PATH}" \
      -DROCM_MAJOR_VERSION="${ROCM_VERSION%%.*}" \
      -DAMD_APP_BUILD_RELOCATABLE_PACKAGE=ON \
      -DAMD_APP_STANDALONE_BUILD_PACKAGE=OFF \
      -DAMD_APP_ROCM_BUILD_PACKAGE=OFF \
      -DCMAKE_INSTALL_PREFIX="/opt/rocm/extras-${ROCM_VERSION%%.*}" \
      -DCPACK_PACKAGING_INSTALL_PREFIX="/opt/rocm/extras-${ROCM_VERSION%%.*}" \
      -DCMAKE_INSTALL_RPATH="\$ORIGIN:\$ORIGIN/../lib:/opt/rocm/lib:/opt/rocm/lib64"

RUN cmake --build ./build -j"$(nproc)"

RUN mkdir /dist && \
    cd ./build && \
    cpack -G DEB && \
    cp ./*.deb /dist/

############# Export deb #############
FROM scratch AS final
COPY --from=build_deb /dist/* /
