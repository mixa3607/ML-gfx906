ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:latest"
ARG ROCM_ARCH="gfx906"

ARG LLAMACPP_REPO="https://github.com/ggml-org/llama.cpp.git"
ARG LLAMACPP_BRANCH="master"
ARG LLAMACPP_COMMIT=""
ARG LLAMACPP_CODE_PATH=""
ARG LLAMACPP_PATCH="empty.patch"
ARG CMAKE_HIP_FLAGS=""
ARG CCACHE_MAXSIZE="2G"

############# Base image #############
FROM ${ROCM_IMAGE} AS rocm_base
# Install basic utilities and Python
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl libgomp1 git python3 python3-venv python3-pip numactl && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 config set global.break-system-packages true && \
    true

ARG ROCM_ARCH
ENV AMDGPU_TARGETS=${ROCM_ARCH}

############# Prepare code #############
FROM rocm_base AS files_llamacpp
ARG LLAMACPP_REPO
ARG LLAMACPP_BRANCH
ARG LLAMACPP_COMMIT
ARG LLAMACPP_CODE_PATH
ARG LLAMACPP_PATCH

# Clone
WORKDIR /files/llamacpp
RUN <<EOF_DOCKERFILE bash
set -eo pipefail
git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${LLAMACPP_BRANCH} ${LLAMACPP_REPO} .
if [ "$LLAMACPP_COMMIT" != "" ]; then 
  git checkout "$LLAMACPP_COMMIT"
fi
if [ "$LLAMACPP_CODE_PATH" != "" ]; then 
  cd "$LLAMACPP_CODE_PATH" && find ./ -maxdepth 1 -mindepth 1 -exec mv -t /files/llamacpp {} +
fi
EOF_DOCKERFILE

# patch
COPY ./patch/${LLAMACPP_PATCH} ./${LLAMACPP_PATCH}
RUN git apply ./${LLAMACPP_PATCH} --allow-empty && rm ./${LLAMACPP_PATCH}

############# Build #############
FROM rocm_base AS build_llamacpp
ARG CMAKE_HIP_FLAGS
ARG CCACHE_MAXSIZE
RUN apt-get update && apt-get install -y build-essential cmake libssl-dev ccache

# build router child wrapper
COPY /extra/child-wrapper/spawn-hook.c /build/child-wrapper/spawn-hook.c
RUN cc -O2 -Wall -Wextra -Werror -shared -fPIC \
    /build/child-wrapper/spawn-hook.c -o /build/child-wrapper/spawn-hook.so -ldl

# build llama.cpp
COPY --from=files_llamacpp /files/llamacpp /build/llamacpp
WORKDIR /build/llamacpp

ENV CCACHE_DIR=/ccache
ENV CCACHE_MAXSIZE=${CCACHE_MAXSIZE}

# https://github.com/ggml-org/llama.cpp/blob/a6206958d28a064564ef132091b9c617ae005f49/ggml/CMakeLists.txt#L221
RUN --mount=type=cache,target=/ccache <<EOF_DOCKERFILE bash
set -eo pipefail

export HIPCXX="$(hipconfig -l)/clang"
export HIP_PATH="$(hipconfig -R)"

CMAKE_ARGS=(
  # BASICS
  -DCMAKE_BUILD_TYPE=Release
  -DLLAMA_BUILD_TESTS=OFF
  # CCACHE
  -DCMAKE_C_COMPILER_LAUNCHER=ccache
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
  # BACKEND
  -DGGML_BACKEND_DL=ON
  -DGGML_NATIVE=OFF
  # BACKEND: HIP
  -DGGML_HIP=ON
  -DGGML_HIP_GRAPHS=ON
  -DGGML_HIP_RCCL=ON
  -DAMDGPU_TARGETS="${ROCM_ARCH}"
  -DCMAKE_HIP_FLAGS="${CMAKE_HIP_FLAGS}"
  # BACKEND: RPC
  -DGGML_RPC=ON
  # BACKEND: CPU
  -DGGML_CPU_ALL_VARIANTS=ON
)

cmake -S . -B build "\${CMAKE_ARGS[@]}"
cmake --build build --config Release -j$(nproc)
EOF_DOCKERFILE
RUN mkdir -p /builded && cp -r /build/child-wrapper ./build/bin/* .devops/tools.sh /builded

############# Copy and install all #############
FROM rocm_base AS final
WORKDIR /app

COPY /extra/requirements-extra.txt /app/requirements-extra.txt
RUN pip3 install -r requirements-extra.txt && pip3 cache purge

COPY --from=build_llamacpp /builded/ /app
COPY /extra/ /app

ENTRYPOINT ["/app/entrypoint.sh"]
