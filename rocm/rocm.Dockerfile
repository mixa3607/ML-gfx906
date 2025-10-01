ARG ROCM_ARCH=gfx906
ARG BASE_ROCM_IMAGE=rocm/dev-ubuntu-24.04:latest

############# Build rocBLAS #############
FROM ${BASE_ROCM_IMAGE} AS rocblas
ARG ROCM_ARCH

WORKDIR /rocblas_files
RUN apt-get update && apt-get install -y git cmake
COPY ./ ./
RUN ROCM_VERSION=$(ls /opt/ | sed -nE 's|rocm-([0-9]+\.[0-9]+\.[0-9]+)|\1|1p') && \
    echo "Detected rocm version is $ROCM_VERSION" && \
    (cd rocBLAS && git checkout rocm-${ROCM_VERSION}) && \
    (cd Tensile && git checkout rocm-${ROCM_VERSION}) && \
    true

WORKDIR /rocblas_files/rocBLAS
RUN ./install.sh --dependencies --rmake_invoked
RUN export ROCM_LIBPATCH_VERSION=$(dpkg -s rocblas | sed -nE 's|^Version: ([0-9]+\.){3}([0-9]+)-(.*)|\2|p') && \
    export CPACK_DEBIAN_PACKAGE_RELEASE=$(dpkg -s rocblas | sed -nE 's|^Version: ([0-9]+\.){3}([0-9]+)-(.*)|\3|p') && \
    echo "Set ROCM_LIBPATCH_VERSION to $ROCM_LIBPATCH_VERSION" && \
    echo "Set CPACK_DEBIAN_PACKAGE_RELEASE to $CPACK_DEBIAN_PACKAGE_RELEASE" && \
    python3 ./rmake.py \
      --install_invoked \
      --build_dir=$(realpath ./build) \
      --src_path=$(realpath .) \
      --architecture $ROCM_ARCH \
      --test_local_path=$(realpath ../Tensile) && \
    true
RUN cd ./build/release && make package
RUN mv "$(find './build/release/' -maxdepth 1 -type f -name 'rocblas_*_amd64.deb')" /rocblas_files/rocblas.deb

############# Patch image #############
FROM ${BASE_ROCM_IMAGE} AS final
RUN --mount=type=bind,from=rocblas,src=/rocblas_files/,target=/rocblas_files \
    dpkg -i /rocblas_files/rocblas.deb && \
    apt-get install && \
    true
