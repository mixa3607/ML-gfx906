ARG BASE_ROCM_IMAGE="docker.io/mixa3607/vllm-gfx906:latest"
ARG ROCM_ARCH="gfx906"
ARG VLLM_REPO="https://github.com/nlzy/vllm-gfx906.git"
ARG VLLM_BRANCH="main"
ARG TRITON_REPO="https://github.com/nlzy/triton-gfx906.git"
ARG TRITON_BRANCH="main"
ARG PYTORCH_REPO="https://github.com/pytorch/pytorch.git"
ARG PYTORCH_BRANCH="v2.7.1"
ARG PYTORCH_VISION_REPO="https://github.com/pytorch/vision.git"
ARG PYTORCH_VISION_BRANCH="v0.21.0"

############# Base image #############
FROM ${BASE_ROCM_IMAGE} AS rocm_base
# Install basic utilities and Python 3.12
RUN apt-get update && apt-get install -y software-properties-common git python3-pip && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update -y && \
    apt-get install -y python3.12 python3.12-dev python3.12-venv \
    python3.12-lib2to3 python-is-python3 python3.12-full && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 1 && \
    update-alternatives --set python3 /usr/bin/python3.12 && \
    ln -sf /usr/bin/python3.12-config /usr/bin/python3-config && \
    python3 -m pip config set global.break-system-packages true && \
    pip install setuptools wheel packaging cmake ninja setuptools_scm jinja2 amdsmi==$(cat /opt/ROCM_VERSION_FULL) && \
    true

# Set environment variables
ARG ROCM_ARCH
ENV ROCM_ARCH=$ROCM_ARCH
ENV PYTORCH_ROCM_ARCH=$ROCM_ARCH
ENV PATH=/opt/rocm/llvm/bin:$PATH
ENV ROCM_PATH=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:
ENV RAY_EXPERIMENTAL_NOSET_ROCR_VISIBLE_DEVICES=1
ENV TOKENIZERS_PARALLELISM=false
ENV HIP_FORCE_DEV_KERNARG=1
ENV VLLM_TARGET_DEVICE=rocm

############# Build torch + vision #############
FROM rocm_base AS build_torch
ARG PYTORCH_REPO
ARG PYTORCH_BRANCH
RUN ls -la /opt/
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${PYTORCH_BRANCH} ${PYTORCH_REPO} pytorch
RUN cd pytorch && pip install -r requirements.txt
#RUN apt install wget -y && wget 'https://repo.radeon.com/rocm/apt/6.4.4/pool/main/r/rocm-llvm/rocm-llvm_19.0.0.25224.60404-129~22.04_amd64.deb' && dpkg -i *.deb 
#RUN ln -s /opt/rocm-6.4.4/llvm /opt/rocm-7.0.0/llvm
# && ls -la /opt/rocm-7.0.0/llvm/* && exit 10
RUN cd pytorch && \
    #export PATH="$(echo "$PATH" | sed 's|/opt/rocm/llvm/bin||1')" && \
    #apt remove rocm-llvm -y && \
    python3 tools/amd_build/build_amd.py && \
    CMAKE_PREFIX_PATH=$(python3 -c 'import sys; print(sys.prefix)') python3 setup.py bdist_wheel --dist-dir=/dist && \
    pip install /dist/*.whl

ARG PYTORCH_VISION_REPO
ARG PYTORCH_VISION_BRANCH
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${PYTORCH_VISION_BRANCH} ${PYTORCH_VISION_REPO} vision
RUN cd vision && python3 setup.py bdist_wheel --dist-dir=/dist \
    && pip install /dist/*.whl

############# Build base #############
FROM rocm_base AS build_base
RUN pip3 install ninja 'cmake<4' wheel pybind11
RUN --mount=type=bind,from=build_torch,src=/dist/,target=/dist \ 
    pip install /dist/*.whl && \
    true

############# Build triton #############
FROM build_base AS build_triton
ARG TRITON_REPO
ARG TRITON_BRANCH
WORKDIR /app
#RUN apt install -y llvm-dev
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
    --mount=type=bind,from=build_torch,src=/dist/,target=/dist_torch \
    --mount=type=bind,from=build_triton,src=/dist/,target=/dist_triton \
    --mount=type=bind,from=build_vllm,src=/dist/,target=/dist_vllm \
    pip install /dist_torch/*.whl /dist_triton/*.whl /dist_vllm/*.whl && \
    pip install -r requirements/rocm.txt  && \
    true

CMD ["/bin/bash"]
