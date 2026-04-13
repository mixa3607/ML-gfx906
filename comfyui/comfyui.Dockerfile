ARG BASE_PYTORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906:v2.7.1-rocm-6.3.3"

ARG COMFY_REPO="https://github.com/ggml-org/llama.cpp.git"
ARG COMFY_BRANCH="master"
ARG COMFY_COMMIT=""

############# Base image #############
FROM ${BASE_PYTORCH_IMAGE} AS torch_base
RUN python3 -m pip config set global.break-system-packages true && \
    apt-get update && apt-get install git curl wget jq aria2 python3-venv -y

############# Clone repos #############
FROM torch_base AS files_comfy
ARG COMFY_REPO
ARG COMFY_BRANCH
ARG COMFY_COMMIT
# Clone
WORKDIR /files/comfy
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${COMFY_BRANCH} ${COMFY_REPO} .
RUN if [ "$COMFY_COMMIT" != "" ]; then git checkout "$COMFY_COMMIT"; fi
COPY /entrypoint.sh /comfyui

FROM files_comfy AS files_comfy_requirements
WORKDIR /files/comfy-requirements
RUN cp /files/comfy/requirements.txt /files/comfy/manager_requirements.txt .
RUN find .

############# Copy and install all #############
FROM torch_base AS final
WORKDIR /comfyui
COPY --from=files_comfy_requirements /files/comfy-requirements /comfyui
RUN pip install huggingface_hub modelscope yq -r requirements.txt -r manager_requirements.txt
COPY --from=files_comfy /files/comfy /comfyui
ENTRYPOINT ["/comfyui/entrypoint.sh"]
