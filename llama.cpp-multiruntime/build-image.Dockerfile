# syntax=docker/dockerfile:1
ARG ROCM_IMAGE="mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14"
ARG CUDA_IMAGE="mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn"

FROM ${CUDA_IMAGE} AS cuda_backend

# Collect the CUDA runtime libraries used by the CUDA backend.
RUN <<EOF_DOCKERFILE bash
set -eu
ldd /app/libggml-cuda.so | grep -Eo "/usr/local/cuda/[^ ]+" | 
  while read -r lib_path; do
    echo "Copy \$lib_path"
    mkdir -p "/cuda-runtime/\$(dirname "\$lib_path")"
    cp -L "\$lib_path" "/cuda-runtime\$lib_path"
  done
EOF_DOCKERFILE

############# Copy cuda libs #############
FROM ${ROCM_IMAGE} AS final

ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

COPY --from=cuda_backend /app/libggml-cuda.so /app/libggml-cuda.so
COPY --from=cuda_backend /cuda-runtime/ /

RUN <<EOF_DOCKERFILE bash
set -eu

echo "Add CUDA to libs"
tee /etc/ld.so.conf.d/cuda.conf <<EOF
# CUDA
/usr/local/cuda/lib64
/usr/local/nvidia/lib
/usr/local/nvidia/lib64
EOF
ldconfig

# libcuda.so.1 is supplied by NVIDIA Container Toolkit when the container starts
ldd /app/libggml-cuda.so | awk '
    /not found/ && \$1 != "libcuda.so.1" {
        missing = 1
        print
    }
    END { exit missing }
'
EOF_DOCKERFILE
