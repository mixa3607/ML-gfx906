# syntax=docker/dockerfile:1
ARG ROCM_IMAGE="mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14@sha256:32ab18dd9c957bb99c1aded8fb93dc40b3fd51b39fc6d142714f51fbc81cfe8c"
ARG CUDA_IMAGE="mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn@sha256:e4d9f6020862b1160406c51403a4629ba1a341e1c4cbfdfc7d0e7a5cc1e3b0cd"

FROM ${CUDA_IMAGE} AS cuda_backend

FROM ${ROCM_IMAGE} AS final
ARG CUDA_CUDART_VERSION="13.3.29-1"
ARG CUDA_CUBLAS_VERSION="13.5.1.27-1"
RUN curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb \
      -o /tmp/cuda-keyring.deb && \
    dpkg -i /tmp/cuda-keyring.deb && rm /tmp/cuda-keyring.deb && \
    apt-get update && apt-get install -y --no-install-recommends \
      "cuda-cudart-13-3=${CUDA_CUDART_VERSION}" \
      "libcublas-13-3=${CUDA_CUBLAS_VERSION}" && \
    rm -rf /var/lib/apt/lists/*
ENV NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    PATH=/app:${PATH} \
    LD_LIBRARY_PATH=/app:/opt/rocm/lib:/usr/local/cuda/lib64:/usr/local/nvidia/lib:/usr/local/nvidia/lib64

COPY --from=cuda_backend /app/libggml-cuda.so /app/libggml-cuda.so
