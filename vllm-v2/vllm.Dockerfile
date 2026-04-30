# Build seq: rocm_base => build_base => build_triton => build_fa => build_vllm => final

ARG BASE_PYTORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906:v2.10.0-rocm-6.3.3"
ARG MAX_JOBS=""
ARG EXTRA_REQUIREMENTS="empty.txt"

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
ENV VLLM_TARGET_DEVICE=rocm
ENV FLASH_ATTENTION_TRITON_AMD_AUTOTUNE=0
ENV FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE

# Install base tools
RUN pip3 install --upgrade --ignore-installed '/opt/rocm/share/amd_smi' pyjwt && \
    pip3 cache purge && \
    apt-get update && apt-get install curl git wget jq aria2 -y

############# Clone repos #############
FROM rocm_base AS files_triton
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

FROM rocm_base AS files_fa
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

FROM rocm_base AS files_vllm
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

FROM rocm_base AS files_extra
ARG EXTRA_REQUIREMENTS
WORKDIR /app/extra-requirements
COPY ./requirements/${EXTRA_REQUIREMENTS} /app/extra-requirements/requirements.txt

############# Build base #############
FROM rocm_base AS build_base
RUN pip3 install build

############# Build triton #############
FROM build_base AS build_triton
COPY --from=files_triton /app/triton /app/triton
WORKDIR /app/triton
RUN pip3 install -r python/requirements.txt
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    pip3 wheel -v --no-deps --no-build-isolation --wheel-dir /dist .
RUN pip3 install /dist/triton-*.whl
RUN ls /dist

############# Build FA #############
FROM build_triton AS build_fa
COPY --from=files_fa /app/flash-attention /app/flash-attention
WORKDIR /app/flash-attention
RUN pip3 install ninja packaging wheel pybind11 psutil
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    pip3 wheel -v --no-deps --no-build-isolation --wheel-dir /dist .
RUN pip3 install /dist/flash_attn-*.whl
RUN ls /dist

############# Build vllm #############
FROM build_fa AS build_vllm
COPY --from=files_vllm /app/vllm /app/vllm
WORKDIR /app/vllm
RUN pip3 install -r requirements/rocm.txt
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    pip3 wheel -v --no-deps --no-build-isolation --wheel-dir /dist .
RUN pip3 install /dist/vllm-*.whl
RUN ls /dist 

############# Install all #############
FROM rocm_base AS final
WORKDIR /app/vllm
RUN --mount=type=bind,from=build_vllm,src=/app/vllm/requirements/,target=/app/vllm/requirements \
    --mount=type=bind,from=files_extra,src=/app/extra-requirements/,target=/app/extra-requirements \
    --mount=type=bind,from=build_vllm,src=/dist/,target=/dist \
    pip3 install /dist/*.whl /dist/flash_attn-*.whl -r /app/vllm/requirements/rocm.txt && \
    pip3 install -r /app/extra-requirements/*.txt && \
    pip3 cache purge && \
    true

CMD ["/bin/bash"]
