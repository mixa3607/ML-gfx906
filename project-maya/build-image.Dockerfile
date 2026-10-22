# syntax=docker/dockerfile:1
ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:10.1-complete"
ARG MAYA_REPO="https://github.com/mw00/project-maya.git"
ARG MAYA_BRANCH="v1.1.21"
ARG MAYA_COMMIT="451f9cb6a21ea65673bdde2e57b4a670ae2b8859"
ARG MAYA_PATCH="gfx906.patch"
ARG MAYA_BUILD_JOBS="4"
ARG CMAKE_HIP_FLAGS=""
ARG CCACHE_MAXSIZE="2G"

############# Base image #############
FROM ${ROCM_IMAGE} AS rocm_base
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bash ca-certificates python3 python3-venv tini libatomic1 libgomp1 git && \
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
  if [ -n "$MAYA_COMMIT" ]; then
      git fetch --depth 1 origin "$MAYA_COMMIT"
      git checkout --detach FETCH_HEAD
  fi
  git rev-parse HEAD > SOURCE_COMMIT
EOF

ARG MAYA_PATCH
COPY patch/${MAYA_PATCH} /tmp/maya.patch
RUN git apply --allow-empty /tmp/maya.patch && rm -rf .git
# The installer pins the llama.cpp sources needed by MMQ and the GGUF tools.
RUN python3 -c 'import setup; setup.get_llama_cpp()'

############# Build #############
FROM rocm_base AS build_maya
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
    -DCMAKE_HIP_ARCHITECTURES=gfx906
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
cmake --build build-hip --target maya maya-ds4 --parallel "$MAYA_BUILD_JOBS"

# Let upstream setup reuse the precompiled engines instead of rebuilding them.
python3 - <<'PY'
import json
import os
from pathlib import Path
import setup

rocm = os.environ['ROCM_PATH']
meta = {
  'backend': 'hip', 
  'src': setup.source_hash(setup.ENGINE_SOURCES),
  'archs': ['gfx906'],
  'rocm': rocm,
  'gpu_ids': [0],
  'llama': str(Path('third_party/llama.cpp').resolve()),
  'lib_dirs': [rocm + '/lib'], 
  'targets': ['maya', 'maya-ds4'],
  'hip_flags': os.environ['CMAKE_HIP_FLAGS']
}
Path('build-hip/MAYA-BUILD.json').write_text(json.dumps(meta, indent=2) + '\n')
PY
EOF

############# Runtime #############
FROM rocm_base AS final
COPY --from=files_maya /opt/maya /opt/maya

RUN python3 -m venv .venv
ENV PATH="/opt/maya/.venv/bin:${PATH}"
RUN python - <<'PY'
import json
from pathlib import Path
import subprocess
import sys
import setup

packages = [p for p in setup.PY_PACKAGES if p not in ('cmake', 'ninja')]
subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *packages,
                'tokenizers', 'huggingface_hub', 'safetensors', './third_party/llama.cpp/gguf-py'], check=True)
# Engines are prebuilt; the installer's build-only dependencies are handled above.
(Path(sys.prefix) / '.strata-pip.json').write_text(json.dumps(setup.PY_PACKAGES + ['tokenizers']))
PY

COPY --from=build_maya /opt/maya/build-hip/maya /opt/maya/build-hip/maya-ds4 /opt/maya/build-hip/MAYA-BUILD.json ./build-hip/
COPY --chmod=755 extra/entrypoint.sh /usr/local/bin/maya
RUN <<'EOF' bash
set -euo pipefail
for binary in build-hip/maya build-hip/maya-ds4; do
    ldd "$binary" > /tmp/maya-ldd.log
    if grep -q 'not found' /tmp/maya-ldd.log; then
        cat /tmp/maya-ldd.log
        exit 1
    fi
done
rm /tmp/maya-ldd.log
EOF

EXPOSE 8080
VOLUME ["/data"]
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/maya"]
CMD ["--help"]
