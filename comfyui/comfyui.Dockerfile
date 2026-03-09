ARG BASE_PYTORCH_IMAGE=docker.io/mixa3607/pytorch-gfx906:v2.7.1-rocm-6.3.3

FROM ${BASE_PYTORCH_IMAGE} AS final
WORKDIR /comfyui
COPY ./requirements.txt ./requirements.txt
RUN pip install -r requirements.txt && \
    pip install huggingface_hub modelscope yq && \
    apt install curl wget jq aria2 -y && \
    true
COPY ./ ./
