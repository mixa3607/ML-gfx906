# syntax=docker/dockerfile:1
ARG BASE_IMAGE="ubuntu:24.04"
ARG ROCM_IMAGE="mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14@sha256:32ab18dd9c957bb99c1aded8fb93dc40b3fd51b39fc6d142714f51fbc81cfe8c"
ARG CUDA_IMAGE="mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn@sha256:e4d9f6020862b1160406c51403a4629ba1a341e1c4cbfdfc7d0e7a5cc1e3b0cd"
ARG LLAMACPP_COMMIT="7fe450e19305b828c199d602c23a8337aaa1f03b"

FROM ${ROCM_IMAGE} AS rocm_backend
ARG LLAMACPP_COMMIT
RUN /app/llama-cli --version > /tmp/llama-version.txt 2>&1 && \
    cat /tmp/llama-version.txt && grep -F "$(printf %.7s "$LLAMACPP_COMMIT")" /tmp/llama-version.txt

FROM ${CUDA_IMAGE} AS cuda_backend
ARG LLAMACPP_COMMIT
RUN /app/llama-cli --version > /tmp/llama-version.txt 2>&1 && \
    cat /tmp/llama-version.txt && grep -F "$(printf %.7s "$LLAMACPP_COMMIT")" /tmp/llama-version.txt

FROM ${BASE_IMAGE} AS build_llamacpp
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build git ca-certificates libssl-dev ccache && \
    rm -rf /var/lib/apt/lists/*
ARG LLAMACPP_REPO="https://github.com/ggml-org/llama.cpp.git"
ARG LLAMACPP_BRANCH="v0.5.0"
ARG LLAMACPP_COMMIT
RUN git clone --depth 1 --branch "$LLAMACPP_BRANCH" "$LLAMACPP_REPO" /src && \
    test "$(git -C /src rev-parse HEAD)" = "$LLAMACPP_COMMIT"
WORKDIR /src
ARG BUILD_JOBS=8
ENV CCACHE_DIR=/ccache
RUN --mount=type=cache,target=/ccache \
    cmake -S . -B build -G Ninja \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_C_COMPILER_LAUNCHER=ccache \
      -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
      -DBUILD_SHARED_LIBS=ON \
      -DGGML_BACKEND_DL=ON \
      -DGGML_NATIVE=OFF \
      -DGGML_CPU_ALL_VARIANTS=ON \
      -DGGML_RPC=ON \
      -DGGML_CUDA=OFF \
      -DGGML_HIP=OFF \
      -DLLAMA_BUILD_TESTS=OFF \
      -DLLAMA_BUILD_EXAMPLES=OFF \
      -DLLAMA_OPENSSL=ON && \
    cmake --build build --parallel "$BUILD_JOBS" && \
    mkdir /out && cp -a build/bin/. /out/ && \
    printf '%s\n' "$LLAMACPP_COMMIT" > /out/llama-commit.txt

FROM ${BASE_IMAGE} AS runtime
ARG ROCM_BUILD="7.14.0-gfx906+20260802001858"
ARG CUDA_CUDART_VERSION="13.3.29-1"
ARG CUDA_CUBLAS_VERSION="13.5.1.27-1"
COPY install-runtime.sh /tmp/install-runtime.sh
RUN bash /tmp/install-runtime.sh && rm /tmp/install-runtime.sh
ENV ROCM_PATH=/opt/rocm \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    PATH=/app:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LD_LIBRARY_PATH=/app:/opt/rocm/lib:/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64

FROM runtime AS final
ARG LLAMACPP_COMMIT
ARG ROCM_IMAGE
ARG CUDA_IMAGE
LABEL org.opencontainers.image.title="llama.cpp CPU + RPC + ROCm gfx906 + CUDA sm120" \
      org.opencontainers.image.source="https://github.com/mixa3607/ML-gfx906/tree/master/llama.cpp-multiruntime" \
      org.opencontainers.image.version="${LLAMACPP_COMMIT}" \
      io.llama.multiruntime.rocm-image="${ROCM_IMAGE}" \
      io.llama.multiruntime.cuda-image="${CUDA_IMAGE}"
WORKDIR /app
COPY --from=build_llamacpp /out/ /app/
COPY --from=rocm_backend /app/libggml-hip.so /app/libggml-hip.so
COPY --from=cuda_backend /app/libggml-cuda.so /app/libggml-cuda.so
COPY --chmod=755 smoke-test.sh /app/smoke-test.sh
# CUDA's libcuda.so.1 comes from the host's NVIDIA container runtime.
RUN <<'EOF'
set -eu
printf '/app\n' > /etc/ld.so.conf.d/llama.conf
ldconfig
for library in /app/*.so*; do
    missing="$(ldd "$library" | grep 'not found' | grep -v 'libcuda.so.1' || true)"
    if [ -n "$missing" ]; then
        printf '%s: %s\n' "$library" "$missing" >&2
        exit 1
    fi
done
/app/llama-cli --version
dpkg-query -W > /app/runtime-packages.txt
EOF
EXPOSE 8080
ENTRYPOINT ["/app/llama-server"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
