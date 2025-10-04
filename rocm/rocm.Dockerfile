ARG ROCM_ARCH="gfx906"
ARG BASE_ROCM_IMAGE="rocm/dev-ubuntu-24.04:6.4.4-complete"
ARG ROCBLAS_REPO="https://github.com/ROCm/rocBLAS"
ARG TENSILE_REPO="https://github.com/ROCm/Tensile"
ARG RCCL_REPO="https://github.com/ROCm/rccl"

############# Base image #############
FROM ${BASE_ROCM_IMAGE} AS rocm_base
# ROCm ver
RUN ROCM_VERSION_MAJOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\1|1p') && \
    ROCM_VERSION_MINOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\2|1p') && \
    ROCM_VERSION_PATCH=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\3|1p') && \
    echo "$ROCM_VERSION_MAJOR" > /opt/ROCM_VERSION_MAJOR && \
    echo "$ROCM_VERSION_MINOR" > /opt/ROCM_VERSION_MINOR && \
    echo "$ROCM_VERSION_PATCH" > /opt/ROCM_VERSION_PATCH && \
    echo "$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR" > /opt/ROCM_VERSION && \
    echo "$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR.$ROCM_VERSION_PATCH" > /opt/ROCM_VERSION_FULL && \
    echo "Detected rocm version is $(cat /opt/ROCM_VERSION_FULL)" && \
    true

############# Build base #############
FROM rocm_base AS build_base
RUN apt-get update && apt-get install -y git cmake libfmt-dev
WORKDIR /rebuild-deps

############# Build rocBLAS #############
FROM build_base AS build_rocblas
ARG ROCBLAS_REPO
ARG TENSILE_REPO
RUN git clone --depth 1 --branch rocm-$(cat /opt/ROCM_VERSION_FULL) ${ROCBLAS_REPO} rocBLAS && \
    git clone --depth 1 --branch rocm-$(cat /opt/ROCM_VERSION_FULL) ${TENSILE_REPO} Tensile && \
    true

WORKDIR /rebuild-deps/rocBLAS
ARG ROCM_ARCH
ENV PACKAGE_NAME=rocblas
RUN dpkg -s ${PACKAGE_NAME}
RUN ./install.sh --dependencies --rmake_invoked
RUN export INSTALLED_PACKAGE_VERSION=$(dpkg -s ${PACKAGE_NAME} | sed -nE 's|^ *Version: (.+)$|\1|p') && \
    echo "Installed package version is \"$INSTALLED_PACKAGE_VERSION\"" && \
    export ROCM_LIBPATCH_VERSION=$(echo "$INSTALLED_PACKAGE_VERSION" | sed -E 's|^([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)-(.*)|\4|1') && \
    echo "Set ROCM_LIBPATCH_VERSION to \"$ROCM_LIBPATCH_VERSION\"" && \
    export CPACK_DEBIAN_PACKAGE_RELEASE=$(echo "$INSTALLED_PACKAGE_VERSION" | sed -E 's|^([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)-(.*)|\5|1') && \
    echo "Set CPACK_DEBIAN_PACKAGE_RELEASE to \"$CPACK_DEBIAN_PACKAGE_RELEASE\"" && \
    python3 ./rmake.py \
      --install_invoked \
      --build_dir=$(realpath ./build) \
      --src_path=$(realpath .) \
      --architecture ${ROCM_ARCH} \
      --test_local_path=$(realpath ../Tensile) && \
    cd ./build/release  && \
    make package && \
    mkdir -p /dist && cp *.deb /dist && \
    true
RUN cd ./build/release && \
    export INSTALLED_PACKAGE_VERSION=$(dpkg -s ${PACKAGE_NAME} | sed -nE 's|^ *Version: (.+)$|\1|p') && \
    export BUILDED_PACKAGE_VERSION=$(dpkg -I /dist/${PACKAGE_NAME}_*.deb | sed -nE 's|^ *Version: (.+)$|\1|p') && \
    if [ "$BUILDED_PACKAGE_VERSION" != "$INSTALLED_PACKAGE_VERSION" ]; then echo "ERR: Builded version is $BUILDED_PACKAGE_VERSION but expected $INSTALLED_PACKAGE_VERSION"; exit 10; fi && \
    true

############# Build rccl #############
FROM build_base AS build_rccl
ARG RCCL_REPO
RUN git clone --depth 1 --branch rocm-$(cat /opt/ROCM_VERSION_FULL) ${RCCL_REPO} rccl && \
    true

WORKDIR /rebuild-deps/rccl
ARG ROCM_ARCH
ENV PACKAGE_NAME=rccl
RUN dpkg -s ${PACKAGE_NAME}
RUN export INSTALLED_PACKAGE_VERSION=$(dpkg -s ${PACKAGE_NAME} | sed -nE 's|^ *Version: (.+)$|\1|p') && \
    echo "Installed package version is \"$INSTALLED_PACKAGE_VERSION\"" && \
    export ROCM_LIBPATCH_VERSION=$(echo "$INSTALLED_PACKAGE_VERSION" | sed -E 's|^([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)-(.*)|\4|1') && \
    echo "Set ROCM_LIBPATCH_VERSION to \"$ROCM_LIBPATCH_VERSION\"" && \
    export CPACK_DEBIAN_PACKAGE_RELEASE=$(echo "$INSTALLED_PACKAGE_VERSION" | sed -E 's|^([0-9]+)\.([0-9]+)\.([0-9]+)\.([0-9]+)-(.*)|\5|1') && \
    echo "Set CPACK_DEBIAN_PACKAGE_RELEASE to \"$CPACK_DEBIAN_PACKAGE_RELEASE\"" && \
    ./install.sh --package_build --amdgpu_targets ${ROCM_ARCH} && \
    mkdir -p /dist && cp ./build/release/*.deb /dist && \
    true
RUN cd ./build/release && \
    export INSTALLED_PACKAGE_VERSION=$(dpkg -s ${PACKAGE_NAME} | sed -nE 's|^ *Version: (.+)$|\1|p') && \
    export BUILDED_PACKAGE_VERSION=$(dpkg -I /dist/${PACKAGE_NAME}_*.deb | sed -nE 's|^ *Version: (.+)$|\1|p') && \
    if [ "$BUILDED_PACKAGE_VERSION" != "$INSTALLED_PACKAGE_VERSION" ]; then echo "ERR: Builded version is $BUILDED_PACKAGE_VERSION but expected $INSTALLED_PACKAGE_VERSION"; exit 10; fi && \
    true

############# Patched image #############
FROM rocm_base AS final
RUN apt-get update && apt-get install -y libfmt-dev
# Install rocblas 
RUN --mount=type=bind,from=build_rocblas,src=/dist/,target=/dist \
    dpkg -i /dist/*.deb
# Install rccl
RUN --mount=type=bind,from=build_rccl,src=/dist/,target=/dist \
    dpkg -i /dist/*.deb

# Validate apt deps state
RUN apt-get install
