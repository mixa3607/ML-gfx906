ARG BASE_ROCM_IMAGE=docker.io/rocm/dev-ubuntu-24.04:latest
ARG BASE_VLLM_IMAGE=docker.io/library/ubuntu:24.04

FROM ${BASE_ROCM_IMAGE} AS rocm_base
# ROCm ver
RUN ROCM_VERSION_MAJOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\1|1p') && \
    ROCM_VERSION_MINOR=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\2|1p') && \
    ROCM_VERSION_PATCH=$(ls /opt/ | sed -nE 's|rocm-([0-9]+)\.([0-9]+)\.([0-9]+)|\3|1p') && \
    echo "$ROCM_VERSION_MAJOR" > /opt/ROCM_VERSION_MAJOR && \
    echo "$ROCM_VERSION_MINOR" > /opt/ROCM_VERSION_MINOR && \
    echo "$ROCM_VERSION_PATCH" > /opt/ROCM_VERSION_PATCH && \
    echo "$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR" > /opt/ROCM_VERSION && \
    echo "$ROCM_VERSION_MAJOR.$ROCM_VERSION_MINOR.$ROCM_VERSION_PATCH" > /opt/ROCM_VERSION_FULL && \
    true

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
    true

# Set environment variables
ENV PATH=/opt/rocm/llvm/bin:$PATH
ENV ROCM_PATH=/opt/rocm
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:
ENV PYTORCH_ROCM_ARCH=gfx906
ENV RAY_EXPERIMENTAL_NOSET_ROCR_VISIBLE_DEVICES=1
ENV TOKENIZERS_PARALLELISM=false
ENV HIP_FORCE_DEV_KERNARG=1
ENV VLLM_TARGET_DEVICE=rocm

# Install pip and configure for ROCm packages
RUN pip install setuptools wheel packaging cmake ninja setuptools_scm amdsmi==$(cat /opt/ROCM_VERSION_FULL) && \
    pip install torch==2.7.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm$(cat /opt/ROCM_VERSION) && \
    TORCH_DIR=$(pip show torch | sed -nE 's|Location: (.*)|\1|1p')/torch && \
    ROCM_VERSION=$(cat /opt/ROCM_VERSION_FULL) && \
    echo "Detected torch dir is $TORCH_DIR" && \
    echo "Detected rocm ver is $ROCM_VERSION" && \
    rm -r $TORCH_DIR/lib/rocblas && \
    ln -s /opt/rocm-$ROCM_VERSION/lib/rocblas $TORCH_DIR/lib/rocblas && \
    true

FROM rocm_base AS build_triton
RUN pip3 install ninja 'cmake<4' wheel pybind11
WORKDIR /vllm/triton
COPY /triton-gfx906 ./
ENV PIP_NO_BUILD_ISOLATION=no
RUN if [ ! -f /tmp/setup.py ]; then cd python; fi; python3 setup.py bdist_wheel --dist-dir=/dist
RUN ls /dist

FROM rocm_base AS vllm_base
WORKDIR /app/vllm
COPY /vllm-gfx906/requirements ./requirements
RUN pip install -r requirements/rocm.txt

FROM vllm_base AS build_vllm
COPY /vllm-gfx906 ./
RUN pip install -r requirements/rocm-build.txt
RUN python3 setup.py bdist_wheel --dist-dir=/dist
RUN ls /dist 

FROM vllm_base AS final
RUN --mount=type=bind,from=build_triton,src=/dist/,target=/dist \
    pip install /dist/*.whl
RUN --mount=type=bind,from=build_vllm,src=/dist/,target=/dist \
    pip install /dist/*.whl
CMD ["/bin/bash"]
