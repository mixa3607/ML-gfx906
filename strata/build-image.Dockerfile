ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:10.1-complete"

ARG STRATA_REPO="https://github.com/Niko1221/Strata.git"
ARG STRATA_BRANCH="v0.2.0-beta"
ARG STRATA_COMMIT=""
ARG STRATA_PATCH="gfx906-setup.patch"
ARG CCACHE_MAXSIZE="2G"

############# Base image #############
FROM ${ROCM_IMAGE} AS rocm_base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      git \
      bash \
      ca-certificates \
      curl \
      libatomic1 \
      libgomp1 \
      python3 \
      python3-pip \
      tini && \
    python3 -m pip config set global.break-system-packages true && \
    rm -rf /var/lib/apt/lists/*

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

############# Prepare code #############
FROM rocm_base AS files_strata
ARG STRATA_REPO
ARG STRATA_BRANCH
ARG STRATA_COMMIT
ARG STRATA_PATCH

WORKDIR /files/strata
COPY patch/${STRATA_PATCH} /tmp/${STRATA_PATCH}
RUN <<EOF_DOCKERFILE bash
set -eo pipefail
git clone --depth 1 --branch "${STRATA_BRANCH}" "${STRATA_REPO}" .
if [ -n "${STRATA_COMMIT}" ]; then
  git fetch --depth 1 origin "${STRATA_COMMIT}"
  git checkout --detach FETCH_HEAD
fi
git apply --allow-empty "/tmp/${STRATA_PATCH}"
rm -f "/tmp/${STRATA_PATCH}"
rm -rf .git bench/results docs/media docs/paper
EOF_DOCKERFILE

############# Build #############
FROM rocm_base AS build_strata
ARG CCACHE_MAXSIZE

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential cmake ninja-build ccache

COPY --from=files_strata /files/strata /opt/strata
WORKDIR /opt/strata

RUN python3 -c 'import setup; setup.get_llama_cpp()'

ENV CCACHE_DIR=/ccache
ENV CCACHE_MAXSIZE=${CCACHE_MAXSIZE}

RUN --mount=type=cache,target=/ccache <<'EOF_DOCKERFILE' bash
set -eo pipefail

CMAKE_COMMON_ARGS=(
  -DCMAKE_BUILD_TYPE=Release
  -DCMAKE_C_COMPILER="$ROCM_PATH/llvm/bin/clang"
  -DCMAKE_CXX_COMPILER="$ROCM_PATH/llvm/bin/clang++"
  -DCMAKE_C_COMPILER_LAUNCHER=ccache
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
  -DSTRATA_PORTABLE=ON
)

CMAKE_HIP_ARGS=(
  "${CMAKE_COMMON_ARGS[@]}"
  -DCMAKE_HIP_ARCHITECTURES=gfx906
  -DCMAKE_HIP_COMPILER="$ROCM_PATH/llvm/bin/clang++"
  -DCMAKE_HIP_COMPILER_LAUNCHER=ccache
  -DCMAKE_HIP_COMPILER_ROCM_ROOT="$ROCM_PATH"
  -DCMAKE_PREFIX_PATH="$ROCM_PATH"
)

CMAKE_ARGS=(
  "${CMAKE_HIP_ARGS[@]}"
  -DSTRATA_HIP_GFX906=ON
  -DSTRATA_ENABLE_HIP=OFF
  -DSTRATA_BUILD_TESTS=OFF
  -DSTRATA_GGML_DIR="$PWD/third_party/llama.cpp"
)
cmake -S . -B build -G Ninja "${CMAKE_ARGS[@]}"
cmake --build build --target strata --parallel "$(nproc)"

CMAKE_ARGS=(
  "${CMAKE_COMMON_ARGS[@]}"
  -DSTRATA_VISION_CUDA=OFF
  -DLLAMA_DIR="$PWD/third_party/llama.cpp"
)
cmake -S tools/vision -B build-vision -G Ninja "${CMAKE_ARGS[@]}"
cmake --build build-vision --target strata-vision --parallel "$(nproc)"

CMAKE_ARGS=(
  "${CMAKE_HIP_ARGS[@]}"
  -DSTRATA_VISION_HIP=ON
  -DSTRATA_VISION_HIP_ARCHS=gfx906
  -DLLAMA_DIR="$PWD/third_party/llama.cpp"
)
cmake -S tools/vision -B build-vision-hip -G Ninja "${CMAKE_ARGS[@]}"
cmake --build build-vision-hip --target strata-vision --parallel "$(nproc)"

mkdir -p engine
cp build/strata build-vision/bin/strata-vision build-vision-hip/bin/strata-vision-hip engine/
EOF_DOCKERFILE

RUN python3 - <<'PY'
import json
import setup

meta = {
    "source": "local-hip",
    "backend": "hip",
    "version": setup.source_version(),
    "archs": ["gfx906"],
    "vision": "gpu",
    "vision_archs": ["gfx906"],
    "vision_gpu": setup.HVEXE,
    "vision_cpu": setup.VEXE,
    "lib_dirs": ["/opt/rocm/lib"],
    "src": setup.source_hash(setup.ENGINE_SOURCES),
    "vision_src": setup.source_hash(setup.VISION_SOURCES),
}
(setup.ROOT / "engine" / "BUILD.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
PY

RUN python3 packaging/package_engine.py \
      --src engine --backend hip --arch gfx906 \
      --version "$(python3 -c 'import setup; print(setup.source_version())')" \
      --variant gfx906 --out /components/engine \
      --allow-lib libhipblas.so.3 \
      --allow-lib librocblas.so.5 \
      --allow-lib libamdhip64.so.7

############# Copy and install all #############
FROM rocm_base AS final
WORKDIR /opt/strata/terminal

COPY --from=files_strata /files/strata /opt/strata/terminal
RUN python3 -m pip install --no-cache-dir -r requirements.txt -r requirements-monitor.txt

COPY --from=build_strata /components/engine /opt/strata/components/engine
COPY --from=build_strata /opt/strata/third_party/llama.cpp/ggml/CMakeLists.txt /opt/strata/seed/third_party/llama.cpp/ggml/CMakeLists.txt
COPY --from=build_strata /opt/strata/third_party/llama.cpp/gguf-py /opt/strata/seed/third_party/llama.cpp/gguf-py
COPY --from=files_strata /files/strata/docker/entrypoint.sh /files/strata/docker/healthcheck.sh /opt/strata/
COPY --from=files_strata /files/strata/docker/strata-wrapper.sh /usr/local/bin/strata

# ROCm libraries are supplied by the base image, not duplicated in the component.
RUN <<'EOF_DOCKERFILE' bash
set -eo pipefail
for component in /opt/strata/components/engine/*; do
  python3 -c 'import sys; from pathlib import Path; from strata_control import engine_component as ec; ec.verify(ec.read_manifest(Path(sys.argv[1])), full=True)' "$component"
  for binary in "$component"/strata "$component"/strata-vision "$component"/strata-vision-hip; do
    ldd "$binary" > /tmp/strata-ldd.log
    if grep -q 'not found' /tmp/strata-ldd.log; then
      cat /tmp/strata-ldd.log
      exit 1
    fi
  done
done
rm -f /tmp/strata-ldd.log
EOF_DOCKERFILE

ENV STRATA_COMPONENTS_DIR=/opt/strata/components \
    STRATA_INSTALL_DIR=/data/install \
    XDG_STATE_HOME=/data/state \
    XDG_CONFIG_HOME=/data/config \
    HOME=/data/home \
    PORT=8080 \
    LANG=C.UTF-8 \
    PYTHONNOUSERSITE=1 \
    STRATA_IN_DOCKER=1

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=8s --start-period=2h --retries=3 CMD ["/opt/strata/healthcheck.sh"]

STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/strata/entrypoint.sh"]
CMD ["run"]
