# syntax=docker/dockerfile:1
ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:10.1-complete"
FROM ${ROCM_IMAGE} AS base
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash ca-certificates git curl python3 python3-venv tini libatomic1 libgomp1 \
      build-essential cmake ninja-build ccache && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /opt/maya

FROM base AS source
ARG MAYA_REPO="https://github.com/mw00/project-maya.git"
ARG MAYA_BRANCH="v1.1.21"
ARG MAYA_COMMIT="451f9cb6a21ea65673bdde2e57b4a670ae2b8859"
COPY patch/gfx906.patch /tmp/gfx906.patch
RUN <<'EOF' bash
set -euo pipefail
git clone --depth 1 --branch "$MAYA_BRANCH" "$MAYA_REPO" .
if [ -n "$MAYA_COMMIT" ]; then
    git fetch --depth 1 origin "$MAYA_COMMIT"
    git checkout --detach FETCH_HEAD
fi
git apply /tmp/gfx906.patch
git rev-parse HEAD > SOURCE_COMMIT
python3 -c 'import setup; setup.get_llama_cpp()'
python3 -m venv .venv
.venv/bin/python - <<'PY'
import subprocess
import setup
packages = [p for p in setup.PY_PACKAGES if p not in ('cmake', 'ninja')]
subprocess.run(['.venv/bin/pip', 'install', '--no-cache-dir', *packages, 'tokenizers', 'huggingface_hub', 'safetensors', './third_party/llama.cpp/gguf-py'], check=True)
PY
rm -rf .git
EOF
ENV PATH="/opt/maya/.venv/bin:${PATH}"

FROM source AS experiment
ARG MAYA_EXPERIMENT=""
COPY patch/experiments/ /tmp/maya-experiments/
RUN MAYA_EXPERIMENT="$MAYA_EXPERIMENT" python - <<'PY'
import hashlib
import json
import os
from pathlib import Path
import subprocess
name = os.environ['MAYA_EXPERIMENT']
meta = {'name': name, 'patch_sha256': None}
if name:
    if name not in ('pr297', 'pr377', 'pr377-360'):
        raise SystemExit('Unknown MAYA_EXPERIMENT: ' + name)
    if Path('SOURCE_COMMIT').read_text().strip() != 'ffe2e5e53fd5254e7f3492a20e8ad2b51b26a197':
        raise SystemExit('Experimental patches require the pinned v1.1.22 source')
    patch = Path('/tmp/maya-experiments') / (name + '.patch')
    subprocess.run(['git', 'apply', '--check', str(patch)], check=True)
    subprocess.run(['git', 'apply', str(patch)], check=True)
    meta['patch_sha256'] = hashlib.sha256(patch.read_bytes()).hexdigest()
Path('SOURCE_EXPERIMENT.json').write_text(json.dumps(meta, indent=2) + '\n')
PY

FROM experiment AS build
ARG MAYA_BUILD_JOBS="4"
ARG CMAKE_HIP_FLAGS=""
ENV CCACHE_DIR=/ccache CCACHE_MAXSIZE=2G
COPY test/wave64.cpp /tmp/wave64.cpp
RUN --mount=type=cache,target=/ccache <<'EOF' bash
set -euo pipefail
cmake -S . -B build-hip -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_C_COMPILER="$ROCM_PATH/llvm/bin/clang" \
    -DCMAKE_CXX_COMPILER="$ROCM_PATH/llvm/bin/clang++" \
    -DCMAKE_HIP_COMPILER="$ROCM_PATH/llvm/bin/clang++" \
    -DCMAKE_C_COMPILER_LAUNCHER=ccache \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
    -DCMAKE_HIP_COMPILER_LAUNCHER=ccache \
    -DCMAKE_PREFIX_PATH="$ROCM_PATH" \
    -DCMAKE_HIP_COMPILER_ROCM_ROOT="$ROCM_PATH" \
    -DCMAKE_HIP_ARCHITECTURES=gfx906 \
    -DCMAKE_HIP_FLAGS="$CMAKE_HIP_FLAGS" \
    -DSTRATA_ENABLE_HIP=ON -DSTRATA_ENABLE_CUDA=OFF \
    -DSTRATA_PREFILL_MMQ=ON -DSTRATA_NATIVE_EXPERTS=ON \
    -DSTRATA_PORTABLE=ON -DSTRATA_BUILD_TESTS=ON \
    -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp"
cmake --build build-hip --parallel "$MAYA_BUILD_JOBS"
"$ROCM_PATH/bin/hipcc" --offload-arch=gfx906 -O2 -std=c++17 \
    -DSTRATA_HIP_WAVE64=1 -Iinclude \
    -include include/strata/hip_compat/cuda_runtime.h \
    /tmp/wave64.cpp -o build-hip/gfx906-wave64
python - <<'PY'
import json
import os
import setup
meta = {'backend': 'hip', 'src': setup.source_hash(setup.ENGINE_SOURCES),
        'archs': ['gfx906'], 'rocm': os.environ['ROCM_PATH'], 'gpu_ids': [0],
        'llama': '/opt/maya/third_party/llama.cpp',
        'lib_dirs': [os.environ['ROCM_PATH'] + '/lib'], 'targets': ['maya', 'maya-ds4'],
         'hip_flags': os.environ.get('CMAKE_HIP_FLAGS', ''),
         'experiment': json.load(open('SOURCE_EXPERIMENT.json'))}
with open('build-hip/MAYA-BUILD.json', 'w') as f:
    json.dump(meta, f, indent=1)
PY
for binary in build-hip/maya build-hip/maya-ds4; do
    ldd "$binary" > /tmp/ldd.log
    if grep -q 'not found' /tmp/ldd.log; then cat /tmp/ldd.log; exit 1; fi
done
EOF

FROM experiment AS runtime
COPY --from=build /opt/maya/build-hip/maya /opt/maya/build-hip/maya-ds4 /opt/maya/build-hip/MAYA-BUILD.json ./build-hip/
COPY entrypoint.sh /usr/local/bin/maya
# The installer records Python dependencies here; cmake/ninja are supplied by apt.
# Avoid a redundant pip install (and network dependency) during model setup.
RUN chmod +x /usr/local/bin/maya && python - <<'PY'
import json
import sys
from pathlib import Path
import setup
(Path(sys.prefix) / '.strata-pip.json').write_text(json.dumps(setup.PY_PACKAGES + ['tokenizers']))
PY
ENV HSA_XNACK=0
EXPOSE 8080
VOLUME ["/data"]
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/maya"]
CMD ["--help"]

FROM runtime AS test
COPY --from=build /opt/maya/build-hip ./build-hip
COPY test/run.sh /usr/local/bin/maya-test
RUN chmod +x /usr/local/bin/maya-test
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/maya-test"]
CMD []

FROM runtime AS final
