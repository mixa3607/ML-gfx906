ARG BASE_ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:latest"

############# Base image #############
FROM ${BASE_ROCM_IMAGE} AS rocm_base
# Install basic utilities and Python
RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  apt-get update
  apt-get install -y git python3 python3-venv python3-pip python3-dev pkg-config libdrm-dev
  python3 -m pip config set global.break-system-packages true
  python3 -m pip install uv
EOF_DOCKERFILE

# Set environment variables
ARG ROCM_ARCH="gfx906"
ENV PYTORCH_ROCM_ARCH=$ROCM_ARCH
ENV PATH=/opt/rocm/llvm/bin:$PATH
ENV USE_ROCM=ON
ENV USE_FLASH_ATTENTION=OFF
ENV USE_MEM_EFF_ATTENTION=OFF
ENV UV_BREAK_SYSTEM_PACKAGES=true

############# Build torch #############
FROM rocm_base AS build_torch
WORKDIR /build/pytorch
RUN uv pip install --system build setuptools setuptools_scm wheel packaging cmake==3.28.4 ninja jinja2

ARG PYTORCH_REPO="https://github.com/pytorch/pytorch.git"
ARG PYTORCH_BRANCH="v2.13.0"
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch "${PYTORCH_BRANCH}" "${PYTORCH_REPO}" .
RUN uv pip install --system -r requirements.txt
RUN bash .ci/docker/common/install_mkl.sh

ENV MKLROOT=/opt/intel
ENV CMAKE_INCLUDE_PATH=/opt/intel/include
ENV CMAKE_LIBRARY_PATH=/opt/intel/lib:/lib
ENV BLAS=MKL
ENV USE_STATIC_MKL=ON
RUN python3 tools/amd_build/build_amd.py

ARG MAX_JOBS=""
ARG VERSION_SUFFIX=$ROCM_ARCH
RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  VERSION="$(cat version.txt | sed -E 's/(a|b|rc)[0-9]+$//1')"
  PYTORCH_BUILD_VERSION="${VERSION}+${VERSION_SUFFIX}"
  echo "$PYTORCH_BUILD_VERSION" > /torch-version.txt
EOF_DOCKERFILE

RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  export MAX_JOBS="${MAX_JOBS:-$(nproc)}"
  export PYTORCH_BUILD_VERSION="$(cat /torch-version.txt)"
  export PYTORCH_BUILD_NUMBER="0"
  export CMAKE_PREFIX_PATH="$(python3 -c 'import sys; print(sys.prefix)')"
  python3 -m build --wheel --no-isolation --outdir /dist
EOF_DOCKERFILE

RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  uv pip install --system /dist/*.whl
  python3 -I <<'PY'
import torch
assert torch.backends.mkl.is_available(), "PyTorch was built without MKL"
assert torch._C.has_lapack, "PyTorch was built without LAPACK"
PY
EOF_DOCKERFILE

############# Build vision #############
FROM build_torch AS build_vision
WORKDIR /build/vision
ARG PYTORCH_VISION_REPO="https://github.com/pytorch/vision.git"
ARG PYTORCH_VISION_BRANCH=""
RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  if [ "${PYTORCH_VISION_BRANCH}" = "" ]; then
    git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 "${PYTORCH_VISION_REPO}" .
    git fetch --depth=1 origin "$(cat /build/pytorch/.github/ci_commit_pins/vision.txt)"
    git checkout "$(cat /build/pytorch/.github/ci_commit_pins/vision.txt)"
    git reset --hard FETCH_HEAD
  else
    git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch "${PYTORCH_VISION_BRANCH}" "${PYTORCH_VISION_REPO}" .
  fi
EOF_DOCKERFILE

RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  export MAX_JOBS="${MAX_JOBS:-$(nproc)}"
  export VERSION="$(cat version.txt | sed -E 's/(a|b|rc)[0-9]+$//1')"
  export BUILD_VERSION="${VERSION}+${VERSION_SUFFIX}"
  export PYTORCH_VERSION="$(cat /torch-version.txt)"
  export FORCE_CUDA=1
  python3 -m build --wheel --no-isolation --outdir /dist
EOF_DOCKERFILE
RUN uv pip install --system /dist/*.whl

############# Build audio #############
FROM build_torch AS build_audio
WORKDIR /build/audio
ARG PYTORCH_AUDIO_REPO="https://github.com/pytorch/audio.git"
ARG PYTORCH_AUDIO_BRANCH=""
RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  if [ "${PYTORCH_AUDIO_BRANCH}" = "" ]; then
    git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 "${PYTORCH_AUDIO_REPO}" .
    git fetch --depth=1 origin "$(cat /build/pytorch/.github/ci_commit_pins/audio.txt)"
    git checkout "$(cat /build/pytorch/.github/ci_commit_pins/audio.txt)"
    git reset --hard FETCH_HEAD
  else
    git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch "${PYTORCH_AUDIO_BRANCH}" "${PYTORCH_AUDIO_REPO}" .
  fi
EOF_DOCKERFILE

RUN <<'EOF_DOCKERFILE' bash
  set -eo pipefail
  export MAX_JOBS="${MAX_JOBS:-$(nproc)}"
  export VERSION="$(cat version.txt | sed -E 's/(a|b|rc)[0-9]+$//1')"
  export BUILD_VERSION="${VERSION}+${VERSION_SUFFIX}"
  export PYTORCH_VERSION="$(cat /torch-version.txt)"
  python3 -m build --wheel --no-isolation --outdir /dist
EOF_DOCKERFILE
RUN uv pip install --system /dist/*.whl

############# Export whl #############
FROM scratch AS final
COPY --from=build_torch  /dist/* /
COPY --from=build_vision /dist/* /
COPY --from=build_audio  /dist/* /
