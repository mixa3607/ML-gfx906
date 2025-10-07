ARG BASE_ROCM_IMAGE=docker.io/mixa3607/rocm-gfx906:6.4.4-complete
ARG BASE_COMFY_IMAGE=docker.io/library/ubuntu:24.04

FROM ${BASE_ROCM_IMAGE} AS rocm
RUN echo "Detected rocm version is $(cat /opt/ROCM_VERSION_FULL)" && \
    mkdir -p /comfy-rocm/rocm/lib && \
    cp -R /opt/rocm-$(cat /opt/ROCM_VERSION_FULL)/lib/rocblas /comfy-rocm/rocm/lib && \
    cp -R /opt/ROCM_* /comfy-rocm && \
    true

FROM ${BASE_COMFY_IMAGE} AS final
WORKDIR /comfyui
COPY --from=rocm /comfy-rocm /opt
COPY ./requirements.txt ./requirements.txt
RUN apt-get update && apt-get install -y python3-pip && \
    python3 -m pip config set global.break-system-packages true && \
    (pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm$(cat /opt/ROCM_VERSION) || \
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/rocm$(cat /opt/ROCM_VERSION)) && \
    pip install -r requirements.txt && \
    TORCH_DIR=$(pip show torch | sed -nE 's|Location: (.*)|\1|1p')/torch && \
    echo "Detected torch dir is $TORCH_DIR" && \
    rm -r $TORCH_DIR/lib/rocblas && \
    ln -s /opt/rocm/lib/rocblas $TORCH_DIR/lib/rocblas && \
    true

COPY ./ ./
