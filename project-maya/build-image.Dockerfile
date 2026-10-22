# syntax=docker/dockerfile:1
ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:10.1-complete"
ARG ROCM_ARCH="gfx906"
ARG MAYA_REPO="https://github.com/mw00/project-maya.git"
ARG MAYA_BRANCH="v1.1.24"
ARG MAYA_COMMIT
ARG MAYA_PATCH="gfx906.patch"
ARG MAYA_BUILD_JOBS
ARG CMAKE_HIP_FLAGS=""
ARG CCACHE_MAXSIZE="2G"

############# Base image #############
FROM ${ROCM_IMAGE} AS rocm_base
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bash ca-certificates curl python3 python3-venv tini libatomic1 libgomp1 git && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
WORKDIR /opt/maya

############# Prepare code #############
FROM rocm_base AS files_maya
ARG MAYA_REPO
ARG MAYA_BRANCH
ARG MAYA_COMMIT

RUN <<'EOF' bash
  set -euo pipefail
  git clone --depth 1 --branch "$MAYA_BRANCH" "$MAYA_REPO" .
  if [ -n "${MAYA_COMMIT:-}" ]; then
      git fetch --depth 1 origin "$MAYA_COMMIT"
      git checkout --detach FETCH_HEAD
  fi
  git rev-parse HEAD > SOURCE_COMMIT
EOF

ARG MAYA_PATCH
COPY patch/${MAYA_PATCH} /tmp/maya.patch
RUN git apply --allow-empty /tmp/maya.patch && rm -rf .git
RUN python3 -c 'import setup; setup.get_llama_cpp()'
RUN python3 tools/vision/glm5next_patch.py third_party/llama.cpp

############# Build #############
FROM rocm_base AS build_maya
ARG ROCM_ARCH
ARG MAYA_BUILD_JOBS
ARG CMAKE_HIP_FLAGS
ARG CCACHE_MAXSIZE

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential cmake ninja-build ccache && \
    rm -rf /var/lib/apt/lists/*
COPY --from=files_maya /opt/maya /opt/maya

ENV CCACHE_DIR=/ccache CCACHE_MAXSIZE=${CCACHE_MAXSIZE}
RUN --mount=type=cache,target=/ccache <<'EOF' bash
set -euo pipefail
CMAKE_ARGS=(
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_C_COMPILER="$ROCM_PATH/llvm/bin/clang"
    -DCMAKE_CXX_COMPILER="$ROCM_PATH/llvm/bin/clang++"
    -DCMAKE_HIP_COMPILER="$ROCM_PATH/llvm/bin/clang++"
    -DCMAKE_C_COMPILER_LAUNCHER=ccache
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
    -DCMAKE_HIP_COMPILER_LAUNCHER=ccache
    -DCMAKE_PREFIX_PATH="$ROCM_PATH"
    -DCMAKE_HIP_COMPILER_ROCM_ROOT="$ROCM_PATH"
    -DCMAKE_HIP_ARCHITECTURES="$ROCM_ARCH"
    -DCMAKE_HIP_FLAGS="$CMAKE_HIP_FLAGS"
    -DSTRATA_ENABLE_HIP=ON
    -DSTRATA_ENABLE_CUDA=OFF
    -DSTRATA_PREFILL_MMQ=ON
    -DSTRATA_NATIVE_EXPERTS=ON
    -DSTRATA_PORTABLE=ON
    -DSTRATA_BUILD_TESTS=OFF
    -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp"
)
cmake -S . -B build-hip -G Ninja "${CMAKE_ARGS[@]}"
cmake --build build-hip --target maya maya-ds4 --parallel "${MAYA_BUILD_JOBS:-$(nproc)}"

# Let upstream setup reuse the precompiled engines instead of rebuilding them.
python3 - <<'PY'
import json
import os
from pathlib import Path
import setup

rocm = str(Path(os.environ.get('ROCM_PATH', '/opt/rocm')).resolve())
meta = {
  'backend': 'hip',
  'src': setup.source_hash(setup.ENGINE_SOURCES),
  'archs': os.environ['ROCM_ARCH'].split(';'),
  'rocm': rocm,
  'gpu_ids': [0],
  'llama': str(Path('third_party/llama.cpp').resolve()),
  'lib_dirs': [rocm + '/lib'],
  'targets': ['maya', 'maya-ds4'],
}
Path('build-hip/MAYA-BUILD.json').write_text(json.dumps(meta, indent=1) + '\n')
PY
EOF

RUN --mount=type=cache,target=/ccache <<'EOF' bash
set -euo pipefail
cmake -S tools/vision -B build-vision-cpu -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLAMA_DIR="$PWD/third_party/llama.cpp" \
    -DSTRATA_PORTABLE=ON -DSTRATA_VISION_CUDA=OFF \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
cmake --build build-vision-cpu --target maya-vision --parallel "${MAYA_BUILD_JOBS:-$(nproc)}"
EOF

############# Runtime #############
FROM rocm_base AS final
# `setup` checks for a host C++ compiler even when it reuses the prebuilt
# engines; keep one so the advertised setup path works. Ninja comes from pip;
# make is the fallback generator.
RUN apt-get update && \
    apt-get install -y --no-install-recommends g++ make && \
    rm -rf /var/lib/apt/lists/*
ENV CMAKE_GENERATOR=Ninja
RUN python3 -m venv .venv
ENV PATH="/opt/maya/.venv/bin:${PATH}"
COPY --from=files_maya /opt/maya /opt/maya
COPY --from=build_maya /opt/maya/build-hip/maya /opt/maya/build-hip/maya-ds4 /opt/maya/build-hip/MAYA-BUILD.json ./build-hip/
COPY --from=build_maya /opt/maya/build-vision-cpu/bin/maya-vision ./build-vision-cpu/bin/
COPY extra/ /opt/maya/extra/
RUN /opt/maya/extra/install-python-deps.sh && /opt/maya/extra/validate-build.sh

EXPOSE 8080
VOLUME ["/data"]
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/maya/extra/entrypoint.sh"]
CMD ["--help"]
