# Build seq: rocm_base => build_base => build_triton => build_fa => build_vllm => final

ARG BASE_PYTORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906:v2.10.0-rocm-6.3.3"
ARG MAX_JOBS=""

ARG VLLM_REPO="https://github.com/ai-infos/vllm-gfx906-mobydick.git"
ARG VLLM_BRANCH="main"
ARG VLLM_COMMIT=""
ARG VLLM_PATCH="empty.patch"

ARG TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"
ARG TRITON_BRANCH="main"
ARG TRITON_COMMIT=""
ARG TRITON_PATCH="empty.patch"

ARG FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"
ARG FA_BRANCH="main"
ARG FA_COMMIT=""
ARG FA_PATCH="empty.patch"

############# Base image #############
FROM ${BASE_PYTORCH_IMAGE} AS rocm_base

# Set environment variables
ENV PYTORCH_ROCM_ARCH=$ROCM_ARCH
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:
ENV RAY_EXPERIMENTAL_NOSET_ROCR_VISIBLE_DEVICES=1
ENV TOKENIZERS_PARALLELISM=false
ENV HIP_FORCE_DEV_KERNARG=1
ENV VLLM_TARGET_DEVICE=rocm
ENV FLASH_ATTENTION_TRITON_AMD_AUTOTUNE=0
ENV FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE

# Install base tools
RUN pip3 install                      \
      'packaging>=24.2'               \
      'jinja2>=3.1.6'                 \
      'timm>=1.0.17'                  \
      '/opt/rocm/share/amd_smi'
RUN apt install curl wget jq aria2 -y

############# Build base #############
FROM rocm_base AS build_base
RUN pip3 install                      \
      'cmake>=3.26.1,<4'              \
      'setuptools>=77.0.3,<80.0.0'    \
      'setuptools-scm>=8'             \
      'ninja'                         \
      'wheel'                         \
      'pybind11'                      

############# Build triton #############
FROM build_base AS build_triton
RUN --mount=type=bind,from=build_base,src=/tmp,target=/force-sequental-build echo ''

ARG TRITON_REPO
ARG TRITON_BRANCH
ARG TRITON_COMMIT
ARG TRITON_PATCH
# Clone
WORKDIR /app/triton
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${TRITON_BRANCH} ${TRITON_REPO} .
RUN if [ "$TRITON_COMMIT" != "" ]; then git checkout "$TRITON_COMMIT"; fi
# Patch
COPY ./patch/${TRITON_PATCH} ./${TRITON_PATCH}
RUN git apply ./${TRITON_PATCH} --allow-empty
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    python3 setup.py bdist_wheel --dist-dir=/dist
RUN ls /dist

############# Build FA #############
FROM build_base AS build_fa
RUN --mount=type=bind,from=build_triton,src=/tmp,target=/force-sequental-build echo ''

ARG FA_REPO
ARG FA_BRANCH
ARG FA_COMMIT
ARG FA_PATCH
# Clone
WORKDIR /app/flash-attention
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${FA_BRANCH} ${FA_REPO} .
RUN if [ "$FA_COMMIT" != "" ]; then git checkout "$FA_COMMIT"; fi
# Patch
COPY ./patch/${FA_PATCH} ./${FA_PATCH}
RUN git apply ./${FA_PATCH} --allow-empty
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    python3 setup.py bdist_wheel --dist-dir=/dist
RUN ls /dist

############# Build vllm #############
FROM build_base AS build_vllm
RUN --mount=type=bind,from=build_fa,src=/tmp,target=/force-sequental-build echo ''

ARG VLLM_REPO
ARG VLLM_BRANCH
ARG VLLM_COMMIT
ARG VLLM_PATCH
# Clone
WORKDIR /app/vllm
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${VLLM_BRANCH} ${VLLM_REPO} .
RUN if [ "$VLLM_COMMIT" != "" ]; then git checkout "$VLLM_COMMIT"; fi
# Patch
COPY ./patch/${VLLM_PATCH} ./${VLLM_PATCH}
RUN git apply ./${VLLM_PATCH} --allow-empty
# Build
RUN pip install -r requirements/rocm.txt
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    python3 setup.py bdist_wheel --dist-dir=/dist
RUN ls /dist 

############# Install all #############
FROM rocm_base AS final
WORKDIR /app/vllm
RUN --mount=type=bind,from=build_vllm,src=/app/vllm/requirements,target=/app/vllm/requirements \
    pip install -r requirements/rocm.txt && \
    pip install opentelemetry-sdk opentelemetry-api opentelemetry-semantic-conventions-ai opentelemetry-exporter-otlp && \
    pip install modelscope yq && \
    true
RUN --mount=type=bind,from=build_vllm,src=/dist/,target=/dist_vllm \
    --mount=type=bind,from=build_triton,src=/dist/,target=/dist_triton \
    --mount=type=bind,from=build_fa,src=/dist/,target=/dist_fa \
    pip install /dist_triton/*.whl /dist_vllm/*.whl /dist_fa/*.whl && \
    true

CMD ["/bin/bash"]
