ARG BASE_ROCM_IMAGE=docker.io/rocm/dev-ubuntu-24.04:latest
ARG BASE_COMFY_IMAGE=docker.io/library/ubuntu:24.04

FROM ${BASE_ROCM_IMAGE} AS rocm
RUN ROCM_VERSION_MAJOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\1|1p') && \
    ROCM_VERSION_MINOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\2|1p') && \
    ROCM_VERSION_PATCH=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\3|1p') && \
    ROCM_VERSION=$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR.$ROCM_VERSION_PATCH && \
    echo "Detected rocm version is $ROCM_VERSION" && \
    mkdir -p /comfy-rocm/rocm-$ROCM_VERSION/lib && \
    cp -R /opt/rocm-$ROCM_VERSION/lib/rocblas /comfy-rocm/rocm-$ROCM_VERSION/lib && \
    true

FROM ${BASE_COMFY_IMAGE} AS final
WORKDIR /comfyui
COPY --from=rocm /comfy-rocm /opt
COPY ./requirements.txt ./requirements.txt
RUN ROCM_VERSION_MAJOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\1|1p') && \
    ROCM_VERSION_MINOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\2|1p') && \
    ROCM_VERSION_PATCH=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\3|1p') && \
    ROCM_VERSION=$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR.$ROCM_VERSION_PATCH && \
    echo "Detected rocm version is $ROCM_VERSION" && \
    apt-get update && apt-get install -y python3-pip && \
    (pip install --break-system-packages torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR || \
    pip install --break-system-packages --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/rocm$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR) && \
    pip install --break-system-packages -r requirements.txt && \
    TORCH_DIR=$(pip show torch | sed -nE 's|Location: (.*)|\1|1p')/torch && \
    echo "Detected torch dir is $TORCH_DIR" && \
    rm -r $TORCH_DIR/lib/rocblas && \
    ln -s /opt/rocm-$ROCM_VERSION/lib/rocblas $TORCH_DIR/lib/rocblas && \
    true

COPY ./ ./
