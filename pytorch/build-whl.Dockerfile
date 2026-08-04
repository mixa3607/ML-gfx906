ARG BASE_ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:latest"
ARG ROCM_ARCH="gfx906"
ARG VERSION_SUFFIX=$ROCM_ARCH
ARG MAX_JOBS=""

ARG PYTORCH_REPO="https://github.com/pytorch/pytorch.git"
ARG PYTORCH_BRANCH="v2.13.0"

ARG PYTORCH_VISION_REPO="https://github.com/pytorch/vision.git"
ARG PYTORCH_VISION_BRANCH=""

ARG PYTORCH_AUDIO_REPO="https://github.com/pytorch/audio.git"
ARG PYTORCH_AUDIO_BRANCH=""

############# Base image #############
FROM ${BASE_ROCM_IMAGE} AS rocm_base
# Install basic utilities and Python
RUN apt-get update && \
    apt-get install -y git python3 python3-venv python3-pip python3-dev && \
    python3 -m pip config set global.break-system-packages true && \
    rm -rf /var/lib/apt/lists/* && \
    true

# Set environment variables
ARG ROCM_ARCH
ENV ROCM_ARCH=$ROCM_ARCH
ENV PYTORCH_ROCM_ARCH=$ROCM_ARCH
ENV PATH=/opt/rocm/llvm/bin:$PATH
ENV ROCM_PATH=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:
ENV USE_ROCM=ON
ENV USE_FLASH_ATTENTION=OFF
ENV USE_MEM_EFF_ATTENTION=OFF

############# Build torch #############
FROM rocm_base AS build_torch
RUN apt-get install -y \
      'pkg-config'     \
      'libdrm-dev'     
RUN pip install        \
      'setuptools'     \
      'setuptools_scm' \
      'wheel'          \
      'packaging'      \
      'cmake'          \
      'ninja'          \
      'jinja2'             

WORKDIR /build/pytorch

ARG PYTORCH_REPO
ARG PYTORCH_BRANCH
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch "${PYTORCH_BRANCH}" "${PYTORCH_REPO}" .
RUN pip install -r requirements.txt
RUN python3 tools/amd_build/build_amd.py

ARG MAX_JOBS
ARG VERSION_SUFFIX
RUN VERSION="$(cat version.txt | sed -E 's/(a|b|rc)[0-9]+$//1')" && \
    PYTORCH_BUILD_VERSION="${VERSION}+${VERSION_SUFFIX}"         && \
    echo "$PYTORCH_BUILD_VERSION" > /torch-version.txt
RUN MAX_JOBS="${MAX_JOBS:-$(nproc)}"                        \
    PYTORCH_BUILD_VERSION="$(cat /torch-version.txt)"               \
    PYTORCH_BUILD_NUMBER="0"                                        \
    CMAKE_PREFIX_PATH=$(python3 -c 'import sys; print(sys.prefix)') \
    python3 setup.py bdist_wheel --dist-dir=/dist
RUN pip install /dist/*.whl

############# Build vision #############
FROM build_torch AS build_vision
WORKDIR /build/vision
ARG PYTORCH_VISION_REPO
ARG PYTORCH_VISION_BRANCH
RUN if [ "${PYTORCH_VISION_BRANCH}" = "" ]; then \
      git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 "${PYTORCH_VISION_REPO}" . && \
      git fetch --depth=1 origin "$(cat /build/pytorch/.github/ci_commit_pins/vision.txt)" && \ 
      git checkout "$(cat /build/pytorch/.github/ci_commit_pins/vision.txt)" && \
      git reset --hard FETCH_HEAD; \
    else \
      git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch "${PYTORCH_VISION_BRANCH}" "${PYTORCH_VISION_REPO}" . ; \
    fi

ARG MAX_JOBS
ARG VERSION_SUFFIX
RUN MAX_JOBS="${MAX_JOBS:-$(nproc)}"                             \
    VERSION="$(cat version.txt | sed -E 's/(a|b|rc)[0-9]+$//1')" \
    BUILD_VERSION="${VERSION}+${VERSION_SUFFIX}"                 \
    PYTORCH_VERSION="$(cat /torch-version.txt)"                  \
    python3 setup.py bdist_wheel --dist-dir=/dist
RUN pip install /dist/*.whl

############# Build audio #############
FROM build_torch AS build_audio
WORKDIR /build/audio
ARG PYTORCH_AUDIO_REPO
ARG PYTORCH_AUDIO_BRANCH
RUN if [ "${PYTORCH_AUDIO_BRANCH}" = "" ]; then \
      git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 "${PYTORCH_AUDIO_REPO}" . && \
      git fetch --depth=1 origin "$(cat /build/pytorch/.github/ci_commit_pins/audio.txt)" && \ 
      git checkout "$(cat /build/pytorch/.github/ci_commit_pins/audio.txt)" && \
      git reset --hard FETCH_HEAD; \
    else \
      git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch "${PYTORCH_AUDIO_BRANCH}" "${PYTORCH_AUDIO_REPO}" . ; \
    fi

ARG MAX_JOBS
ARG VERSION_SUFFIX
RUN MAX_JOBS="${MAX_JOBS:-$(nproc)}"                             \
    VERSION="$(cat version.txt | sed -E 's/(a|b|rc)[0-9]+$//1')" \
    BUILD_VERSION="${VERSION}+${VERSION_SUFFIX}"                 \
    PYTORCH_VERSION="$(cat /torch-version.txt)"                  \
    python3 setup.py bdist_wheel --dist-dir=/dist
RUN pip install /dist/*.whl

############# Export whl #############
FROM scratch AS final
COPY --from=build_torch  /dist/* /
COPY --from=build_vision /dist/* /
COPY --from=build_audio  /dist/* /
