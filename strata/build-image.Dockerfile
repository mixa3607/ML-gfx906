# syntax=docker/dockerfile:1

ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:10.1-complete"
ARG ROCM_ARCH="gfx906"
ARG STRATA_REPO="https://github.com/Niko1221/Strata.git"
ARG STRATA_BRANCH="v0.2.15"
ARG STRATA_COMMIT=""
ARG STRATA_PATCH="empty.patch"
ARG CMAKE_HIP_FLAGS=""
ARG CCACHE_MAXSIZE="2G"

############# Base image #############
FROM ${ROCM_IMAGE} AS rocm_base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      ca-certificates libatomic1 libgomp1 python3 tini git python3-venv && \
    rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
WORKDIR /opt/strata

############# Prepare code #############
FROM rocm_base AS files_strata
ARG STRATA_REPO
ARG STRATA_BRANCH
ARG STRATA_COMMIT
ARG STRATA_PATCH

RUN <<'EOF' bash
  set -euo pipefail
  git clone --depth 1 --branch "${STRATA_BRANCH}" "${STRATA_REPO}" .
  if [ -n "${STRATA_COMMIT:-}" ]; then
      git fetch --depth 1 origin "$STRATA_COMMIT"
      git checkout --detach FETCH_HEAD
  fi
  git rev-parse HEAD > SOURCE_COMMIT
EOF

COPY patch/${STRATA_PATCH} /tmp/strata.patch
RUN git apply --allow-empty /tmp/strata.patch && rm -rf .git bench/results/ docs/
# Downloads llama.cpp into third_party/llama.cpp for the release trees that still
# need it; a no-op on v0.2.15, which vendors its ggml and llama trees.
RUN python3 -c 'import setup; setup.get_llama_cpp()'

############# Build #############
FROM rocm_base AS build_strata
ARG ROCM_ARCH
ARG CMAKE_HIP_FLAGS
ARG CCACHE_MAXSIZE

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential cmake ninja-build ccache && \
    rm -rf /var/lib/apt/lists/*
COPY --from=files_strata /opt/strata /opt/strata

ENV CCACHE_DIR=/ccache CCACHE_MAXSIZE=${CCACHE_MAXSIZE}
RUN --mount=type=cache,target=/ccache <<'EOF_DOCKERFILE' bash
set -eo pipefail

CMAKE_COMMON_ARGS=(
  -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_C_COMPILER="$ROCM_PATH/llvm/bin/clang"
  -DCMAKE_CXX_COMPILER="$ROCM_PATH/llvm/bin/clang++"
  -DCMAKE_C_COMPILER_LAUNCHER=ccache
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
  -DCMAKE_C_FLAGS="-w"
  -DCMAKE_CXX_FLAGS="-w"
  -DSTRATA_PORTABLE=ON
)

CMAKE_HIP_ARGS=(
  "${CMAKE_COMMON_ARGS[@]}"
  -DCMAKE_HIP_ARCHITECTURES="$ROCM_ARCH"
  -DCMAKE_HIP_COMPILER="$ROCM_PATH/llvm/bin/clang++"
  -DCMAKE_HIP_COMPILER_LAUNCHER=ccache
  -DCMAKE_HIP_FLAGS="${CMAKE_HIP_FLAGS} -w"
  -DCMAKE_HIP_COMPILER_ROCM_ROOT="$ROCM_PATH"
  -DCMAKE_PREFIX_PATH="$ROCM_PATH"
)

# v0.2.15 vendors third_party/strata-ggml and third_party/strata-llama and
# setup.get_llama_cpp() downloads nothing any more, so third_party/llama.cpp only
# exists for the older release trees (v0.2.3.1 and before). Pass the override
# only when the tree is there: pointing -DSTRATA_GGML_DIR / -DLLAMA_DIR at a
# directory that is never created fails the configure step.
LLAMA_OVERRIDE="$PWD/third_party/llama.cpp"

CMAKE_ARGS=(
  "${CMAKE_HIP_ARGS[@]}"
  -DSTRATA_HIP_GFX906=ON
  -DSTRATA_ENABLE_HIP=OFF
  -DSTRATA_BUILD_TESTS=OFF
)
if [ -f "$LLAMA_OVERRIDE/ggml/CMakeLists.txt" ]; then
  CMAKE_ARGS+=(-DSTRATA_GGML_DIR="$LLAMA_OVERRIDE")
fi
cmake -S . -B build -G Ninja "${CMAKE_ARGS[@]}"
cmake --build build --target strata --parallel "$(nproc)"

CMAKE_ARGS=(
  "${CMAKE_COMMON_ARGS[@]}"
  -DSTRATA_VISION_CUDA=OFF
)
if [ -f "$LLAMA_OVERRIDE/ggml/CMakeLists.txt" ]; then
  CMAKE_ARGS+=(-DLLAMA_DIR="$LLAMA_OVERRIDE")
fi
cmake -S tools/vision -B build-vision -G Ninja "${CMAKE_ARGS[@]}"
cmake --build build-vision --target strata-vision --parallel "$(nproc)"

CMAKE_ARGS=(
  "${CMAKE_HIP_ARGS[@]}"
  -DSTRATA_VISION_HIP=ON
  -DSTRATA_VISION_HIP_ARCHS="$ROCM_ARCH"
)
if [ -f "$LLAMA_OVERRIDE/ggml/CMakeLists.txt" ]; then
  CMAKE_ARGS+=(-DLLAMA_DIR="$LLAMA_OVERRIDE")
fi
cmake -S tools/vision -B build-vision-hip -G Ninja "${CMAKE_ARGS[@]}"
cmake --build build-vision-hip --target strata-vision --parallel "$(nproc)"

mkdir -p engine
cp build/strata build-vision/bin/strata-vision build-vision-hip/bin/strata-vision-hip engine/

# Let upstream setup reuse the precompiled engines instead of rebuilding them.
python3 - <<'PY'
import json
import os
from pathlib import Path
import setup

rocm = str(Path(os.environ.get('ROCM_PATH', '/opt/rocm')).resolve())
meta = {
  "source": "local-hip",
  "backend": "hip",
  "version": setup.source_version(),
  "archs": os.environ['ROCM_ARCH'].split(';'),
  "vision": "gpu",
  "vision_archs": os.environ['ROCM_ARCH'].split(';'),
  "vision_gpu": setup.HVEXE,
  "vision_cpu": setup.VEXE,
  "lib_dirs": ["/opt/rocm/lib"],
  "src": setup.source_hash(setup.ENGINE_SOURCES),
  "vision_src": setup.source_hash(setup.VISION_SOURCES),
}
Path(setup.ROOT / "engine" / "BUILD.json").write_text(json.dumps(meta, indent=1) + '\n')
PY
EOF_DOCKERFILE

RUN build_id="$(cat SOURCE_COMMIT 2>/dev/null || echo unknown)" && \
    python3 packaging/stage_tuning.py --stage engine --archs "$ROCM_ARCH" --rocm "$ROCM_PATH" && \
    python3 packaging/package_engine.py \
      --src engine --backend hip --arch "$ROCM_ARCH" \
      --version "$(python3 -c 'import setup; print(setup.source_version())')" \
      --variant "$ROCM_ARCH" --out /out/components/engine \
      --build-id "$build_id" \
      --allow-lib libhipblas.so.3 \
      --allow-lib libhipblaslt.so.1 \
      --allow-lib librocblas.so.5 \
      --allow-lib libamdhip64.so.7 && \
    if [ -f third_party/llama.cpp/ggml/CMakeLists.txt ]; then \
      mkdir -p /out/seed/third_party/llama.cpp/ggml && \
      cp third_party/llama.cpp/ggml/CMakeLists.txt /out/seed/third_party/llama.cpp/ggml/ && \
      cp -a third_party/llama.cpp/gguf-py /out/seed/third_party/llama.cpp/; \
    fi

############# Copy and install all #############
FROM rocm_base AS final
WORKDIR /opt/strata/terminal

# Terminal sources and the container scripts.
COPY --from=files_strata /opt/strata /opt/strata/terminal
COPY --from=build_strata /out/ /opt/strata/
COPY extra/ /opt/strata/
RUN /opt/strata/install-python-deps.sh && /opt/strata/validate-build.sh

ENV STRATA_COMPONENTS_DIR=/opt/strata/components \
    STRATA_INSTALL_DIR=/data/install \
    STRATA_IN_DOCKER=1 \
    XDG_STATE_HOME=/data/state \
    XDG_CONFIG_HOME=/data/config \
    HOME=/data/home \
    PORT=8080 \
    PYTHONNOUSERSITE=1

EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=8s --start-period=2h --retries=3 CMD ["/opt/strata/terminal/docker/healthcheck.sh"]
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/strata/terminal/docker/entrypoint.sh"]
CMD ["run"]
