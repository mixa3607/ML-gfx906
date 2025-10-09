ARG BASE_ROCM_IMAGE="docker.io/mixa3607/vllm-gfx906:latest"
ARG ROCM_ARCH="gfx906"
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
    pip install amdsmi==$(cat /opt/ROCM_VERSION_FULL) && \
    true

# Set environment variables
ARG ROCM_ARCH
ENV ROCM_ARCH=$ROCM_ARCH
ENV PYTORCH_ROCM_ARCH=$ROCM_ARCH
ENV PATH=/opt/rocm/llvm/bin:$PATH
ENV ROCM_PATH=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:

############# Build torch + vision #############
FROM rocm_base AS build_torch
RUN pip install setuptools wheel packaging cmake ninja setuptools_scm jinja2

ARG PYTORCH_REPO
ARG PYTORCH_BRANCH
RUN ls -la /opt/
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${PYTORCH_BRANCH} ${PYTORCH_REPO} pytorch
RUN cd pytorch && pip install -r requirements.txt
RUN cd pytorch && \
    python3 tools/amd_build/build_amd.py && \
    CMAKE_PREFIX_PATH=$(python3 -c 'import sys; print(sys.prefix)') python3 setup.py bdist_wheel --dist-dir=/dist && \
    pip install /dist/*.whl

ARG PYTORCH_VISION_REPO
ARG PYTORCH_VISION_BRANCH
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${PYTORCH_VISION_BRANCH} ${PYTORCH_VISION_REPO} vision
RUN cd vision && python3 setup.py bdist_wheel --dist-dir=/dist \
    && pip install /dist/*.whl

############# Install all #############
FROM rocm_base AS final
RUN --mount=type=bind,from=build_torch,src=/dist/,target=/dist_torch \
    pip install /dist_torch/*.whl && \
    true

CMD ["/bin/bash"]
