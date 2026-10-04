# syntax=docker/dockerfile:1
ARG ROCM_IMAGE="mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14"
ARG CUDA_IMAGE="mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn"

FROM ${CUDA_IMAGE} AS cuda_backend
RUN set -eu; \
    mkdir -p /cuda-runtime; \
    ldd /app/libggml-cuda.so | \
      awk '$3 ~ /^\/usr\/local\/cuda\// { print $1, $3 }' | \
      while read -r soname path; do cp -L "$path" "/cuda-runtime/$soname"; done; \
    test -n "$(ls -A /cuda-runtime)"

FROM ${ROCM_IMAGE} AS final
ENV NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    PATH=/app:${PATH} \
    LD_LIBRARY_PATH=/app:/app/cuda-libs:/opt/rocm/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64

COPY --from=cuda_backend /app/libggml-cuda.so /app/libggml-cuda.so
COPY --from=cuda_backend /cuda-runtime/ /app/cuda-libs/
# libcuda.so.1 is injected by NVIDIA Container Toolkit at runtime.
RUN ldd /app/libggml-cuda.so | \
    awk '/not found/ && $1 != "libcuda.so.1" { missing = 1; print } END { exit missing }'
