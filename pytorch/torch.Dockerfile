ARG BASE_ROCM_IMAGE="docker.io/mixa3607/vllm-gfx906:latest"
ARG ROCM_ARCH="gfx906"
ARG PYTORCH_REPO="https://github.com/pytorch/pytorch.git"
ARG PYTORCH_BRANCH="v2.7.1"
ARG PYTORCH_VISION_REPO="https://github.com/pytorch/vision.git"
ARG PYTORCH_VISION_BRANCH=""
ARG PYTORCH_AUDIO_REPO="https://github.com/pytorch/audio.git"
ARG PYTORCH_AUDIO_BRANCH=""

############# Base image #############
FROM ${BASE_ROCM_IMAGE} AS rocm_base
# Install basic utilities and Python 3.12
RUN apt-get update && apt-get install -y software-properties-common git python3-pip && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update -y && \
    apt-get install -y python3.12 python3.12-dev python3.12-venv \
    python3.12-lib2to3 python-is-python3 python3.12-full && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    update-alternatives --set python3 /usr/bin/python3.12 && \
    ln -sf /usr/bin/python3.12-config /usr/bin/python3-config && \
    python3 -m pip config set global.break-system-packages true && \
    pip install amdsmi==$(cat /opt/ROCM_VERSION_FULL) && \
    true

# Set environment variables
ARG ROCM_ARCH
ENV ROCM_ARCH=$ROCM_ARCH
ENV PYTORCH_ROCM_ARCH=$ROCM_ARCH
ENV PATH=/opt/rocm/llvm/bin:$PATH
ENV ROCM_PATH=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:

############# Build torch #############
FROM rocm_base AS build_torch
RUN pip install setuptools wheel packaging cmake ninja setuptools_scm jinja2

WORKDIR /build/pytorch
ARG PYTORCH_REPO
ARG PYTORCH_BRANCH
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch "${PYTORCH_BRANCH}" "${PYTORCH_REPO}" .
RUN pip install -r requirements.txt
RUN sed -i 's|7e29c325d5bd33ba896ddb106f5d4fc7d715274dca7fe937f724fffa82017838|1e9b3dddf0c7fc07131c6f0f5266129e83ce2331f459fa2be8c63f4ae91b0f5b|g' cmake/External/aotriton.cmake && \
    python3 tools/amd_build/build_amd.py && \
    CMAKE_PREFIX_PATH=$(python3 -c 'import sys; print(sys.prefix)') python3 setup.py bdist_wheel --dist-dir=/dist && \
    pip install /dist/*.whl

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
RUN python3 setup.py bdist_wheel --dist-dir=/dist && \
    pip install /dist/*.whl

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
RUN python3 setup.py bdist_wheel --dist-dir=/dist && \
    pip install /dist/*.whl

############# Install all #############
FROM rocm_base AS final
RUN --mount=type=bind,from=build_torch,src=/dist/,target=/dist_torch \
    --mount=type=bind,from=build_vision,src=/dist/,target=/dist_vision \
    --mount=type=bind,from=build_audio,src=/dist/,target=/dist_audio \
    pip install /dist_torch/*.whl /dist_vision/torchvision-*.whl /dist_audio/torchaudio-*.whl && \
    true

CMD ["/bin/bash"]
