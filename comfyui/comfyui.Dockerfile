ARG BASE_ROCM_IMAGE=rocm/dev-ubuntu-24.04:latest

############# Build rocBLAS #############
FROM ${BASE_ROCM_IMAGE} AS final
WORKDIR /comfyui
COPY ./ ./
RUN ROCM_VERSION_MAJOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\1|1p') && \
    ROCM_VERSION_MINOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\2|1p') && \
    ROCM_VERSION_PATCH=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\3|1p') && \
    echo "Detected rocm version is $ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR.$ROCM_VERSION_PATCH" && \
    pip install --break-package-system torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR && \
    pip install --break-package-system -r requirements.txt && \
    true
