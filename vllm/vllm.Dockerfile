ARG BASE_PYTORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906:v2.7.1-rocm-6.3.3"
ARG VLLM_REPO="https://github.com/nlzy/vllm-gfx906.git"
ARG VLLM_BRANCH="main"
ARG TRITON_REPO="https://github.com/nlzy/triton-gfx906.git"
ARG TRITON_BRANCH="main"

############# Base image #############
FROM ${BASE_PYTORCH_IMAGE} AS rocm_base
# Install basic utilities and Python 3.12
RUN pip install amdsmi==$(cat /opt/ROCM_VERSION_FULL)

# Set environment variables
ENV PYTORCH_ROCM_ARCH=$ROCM_ARCH
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:
ENV RAY_EXPERIMENTAL_NOSET_ROCR_VISIBLE_DEVICES=1
ENV TOKENIZERS_PARALLELISM=false
ENV HIP_FORCE_DEV_KERNARG=1
ENV VLLM_TARGET_DEVICE=rocm

############# Build base #############
FROM rocm_base AS build_base
RUN pip3 install ninja 'cmake<4' wheel pybind11 setuptools_scm

############# Build triton #############
FROM build_base AS build_triton
ARG TRITON_REPO
ARG TRITON_BRANCH
WORKDIR /app
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${TRITON_BRANCH} ${TRITON_REPO} triton
WORKDIR /app/triton
# "if" used for diff between triton 3.3.0<=>3.4.0
RUN if [ ! -f setup.py ]; then cd python; fi; python3 setup.py bdist_wheel --dist-dir=/dist
RUN ls /dist

############# Build vllm #############
FROM build_base AS build_vllm
ARG VLLM_REPO
ARG VLLM_BRANCH
WORKDIR /app
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${VLLM_BRANCH} ${VLLM_REPO} vllm
WORKDIR /app/vllm
RUN pip install -r requirements/rocm.txt
RUN python3 setup.py bdist_wheel --dist-dir=/dist
RUN ls /dist 

############# Install all #############
FROM rocm_base AS final
WORKDIR /app/vllm
RUN --mount=type=bind,from=build_vllm,src=/app/vllm/requirements,target=/app/vllm/requirements \
    --mount=type=bind,from=build_vllm,src=/dist/,target=/dist_vllm \
    --mount=type=bind,from=build_triton,src=/dist/,target=/dist_triton \
    pip install /dist_triton/*.whl /dist_vllm/*.whl && \
    pip install -r requirements/rocm.txt && \
    pip install opentelemetry-sdk opentelemetry-api opentelemetry-semantic-conventions-ai opentelemetry-exporter-otlp && \
    pip install modelscope && \
    true

CMD ["/bin/bash"]
