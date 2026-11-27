# syntax=docker/dockerfile:1

ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:10.1-complete"
ARG ROCM_ARCH="gfx906"
ARG STRATA_REPO="https://github.com/Niko1221/Strata.git"
ARG STRATA_BRANCH="v0.2.22"
ARG STRATA_COMMIT=""
ARG STRATA_PATCH="v0.2.22.patch"
ARG CMAKE_HIP_FLAGS=""
ARG CCACHE_MAXSIZE="2G"
# Which picture reader(s) the component carries: cpu = strata-vision (the CPU
# reader a card under 24 GB of VRAM gets by default, and the fallback of the GPU
# one), gpu = strata-vision-hip, both = the two programs upstream's AMD packages
# carry. cpu is the default here: gfx906 pictures run on the processor, which
# keeps the ~1-1.4 GB of VRAM for the experts and stays off the GPU reader that
# upstream checks on no gfx906 card (docs/AMD_HIP.md).
ARG STRATA_PICTURE_READER="cpu"
# 1: the image also carries strata-hy4 (the Hy4-Flash engine) as its own component
# under components/shapes/hy4/engine/, beside the Strata engine's components/engine/
# (the layout upstream's release images use).  0: strata only.  hy4's GPU sources
# are HIP already, so gfx906 needs the one CMake line the patch carries and no
# compat layer; the engine is compiled and packaged, not run on a card here.
ARG STRATA_BUILD_HY4="1"

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
WORKDIR /src

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
RUN git apply --allow-empty /tmp/strata.patch && rm -rf .git

############# Build #############
FROM rocm_base AS build_strata
ARG ROCM_ARCH
ARG CMAKE_HIP_FLAGS
ARG CCACHE_MAXSIZE
ARG STRATA_PICTURE_READER
ARG STRATA_BUILD_HY4

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential cmake ninja-build ccache && \
    rm -rf /var/lib/apt/lists/*
COPY --from=files_strata /src /src
WORKDIR /src

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

# The engine: the gfx906 source build of docs/AMD_HIP.md (wave64 compat layer,
# STRATA_HIP_GFX906, no wave32 HIP backend).  strata-inkling is off: STRATA_HIP_GFX906
# forces STRATA_ENABLE_CUDA on (every .cu is compiled as HIP) and inkling2's CUDA
# lane reacts to that flag with enable_language(CUDA), which stops configure at
# "Failed to find nvcc" (src/inkling2/CMakeLists.txt:197, new since v0.2.16).  It is
# not part of the package, and upstream's own Dockerfile.src has the same switch.
# strata-hy4 is a second component, not a second image; its GPU sources are HIP, so
# the patch only keeps them from being handed to nvcc (engine/CMakeLists.txt:968).
case "$STRATA_BUILD_HY4" in
0|1) ;;
*)
  echo "STRATA_BUILD_HY4 must be 1 or 0 (got '$STRATA_BUILD_HY4')" >&2
  exit 1
  ;;
esac
hy4=OFF
[ "$STRATA_BUILD_HY4" = "1" ] && hy4=ON
cmake -S engine -B build -G Ninja \
  "${CMAKE_HIP_ARGS[@]}" \
  -DSTRATA_HIP_GFX906=ON \
  -DSTRATA_ENABLE_HIP=OFF \
  -DSTRATA_BUILD_INKLING=OFF \
  -DSTRATA_BUILD_HY4="$hy4" \
  -DSTRATA_BUILD_TESTS=OFF

# tools/packaging/engine_targets.sh answers "strata strata_kq" even where ninja
# rejects strata_kq (its dry-run probe exits 0), so decide from the build graph.
targets="strata"
if grep -qE '^build [^:]*libstrata_kq\.so' build/build.ninja 2>/dev/null; then
  targets="strata strata_kq"
fi
# The Hy4-Flash engine: its own program and its own component (strata-hy4), built
# only when this configure asked for it.
if [ "$hy4" = "ON" ]; then
  grep -qE '^build [^:]*strata-hy4: ' build/build.ninja 2>/dev/null || {
    echo "STRATA_BUILD_HY4=1 but the build graph has no strata-hy4 target" >&2
    exit 1
  }
  targets="$targets strata-hy4"
fi
echo "engine targets: $targets"
cmake --build build --target $targets --parallel "$(nproc)"

# The picture readers: terminal/tools/vision, its own tower as plain C++17 on the
# CPU and on hipBLAS for the card. The CPU program is named strata-vision and is
# the reader a card under 24 GB of VRAM gets by default (strata_control/
# vision_reader.py); the GPU one is strata-vision-hip, built only when asked for.
case "$STRATA_PICTURE_READER" in
cpu|gpu|both) ;;
*)
  echo "STRATA_PICTURE_READER must be cpu, gpu or both (got '$STRATA_PICTURE_READER')" >&2
  exit 1
  ;;
esac

if [ "$STRATA_PICTURE_READER" != "gpu" ]; then
  # No CUDA/HIP switch: this builds the CPU reader, so the program keeps its
  # default name strata-vision.
  cmake -S terminal/tools/vision -B build-vision-cpu -G Ninja \
    "${CMAKE_COMMON_ARGS[@]}" \
    -DSTRATA_PORTABLE=ON
  cmake --build build-vision-cpu --target strata-vision --parallel "$(nproc)"
fi

if [ "$STRATA_PICTURE_READER" != "cpu" ]; then
  # The GPU reader (its own tower on hipBLAS). Upstream checks pictures on no
  # gfx906 card (docs/AMD_HIP.md), which is why this is not the default here.
  cmake -S terminal/tools/vision -B build-vision -G Ninja \
    "${CMAKE_HIP_ARGS[@]}" \
    -DSTRATA_VISION_HIP=ON \
    -DSTRATA_VISION_HIP_ARCHS="$ROCM_ARCH"
  cmake --build build-vision --target strata-vision --parallel "$(nproc)"
fi

mkdir -p /stage
cp build/strata /stage/
[ -f build/libstrata_kq.so ] && cp build/libstrata_kq.so /stage/ || true
# A component without its reader starts text-only, and the `[ -f ] && cp || true`
# used here once dropped the CPU reader for a whole release: stage the reader the
# parameter asked for, and stop the build when it is not there.
if [ "$STRATA_PICTURE_READER" != "gpu" ]; then
  cp build-vision-cpu/bin/strata-vision /stage/
  if [ ! -x /stage/strata-vision ]; then
    echo "the CPU picture reader was not built: ${STRATA_PICTURE_READER} needs build-vision-cpu/bin/strata-vision" >&2
    exit 1
  fi
fi
if [ "$STRATA_PICTURE_READER" != "cpu" ]; then
  cp build-vision/bin/strata-vision-hip /stage/
  if [ ! -x /stage/strata-vision-hip ]; then
    echo "the GPU picture reader was not built: ${STRATA_PICTURE_READER} needs build-vision/bin/strata-vision-hip" >&2
    exit 1
  fi
fi

version="$(sed -n 's/^[[:space:]]*project([^)]*VERSION[[:space:]]*\([0-9][0-9.]*\).*/\1/p' engine/CMakeLists.txt | head -1)"
# vision_archs only when a GPU reader is in the package: the CPU one has no gfx
# code, and the field is what hip_reader() reads as "built for these cards".
vision_archs=""
[ "$STRATA_PICTURE_READER" = "cpu" ] || vision_archs=", \"vision_archs\": \"$ROCM_ARCH\""
cat > /stage/BUILD.json <<JSON
{"version": "${version:-dev}", "source": "docker build", "archs": "$ROCM_ARCH", "portable": true, "vision": "$STRATA_PICTURE_READER"$vision_archs}
JSON
cat /stage/BUILD.json

python3 tools/packaging/stage_tuning.py --stage /stage --archs "$ROCM_ARCH" --rocm "$ROCM_PATH"
python3 tools/packaging/package_engine.py \
  --src /stage --backend hip --arch "$ROCM_ARCH" \
  --version "${version:-dev}" --variant "$ROCM_ARCH" \
  --out /out/components/engine \
  --build-id "$(cat SOURCE_COMMIT 2>/dev/null || echo unknown)" \
  --allow-lib libhipblas.so.3 \
  --allow-lib libhipblaslt.so.1 \
  --allow-lib librocblas.so.5 \
  --allow-lib libamdhip64.so.7

# The Hy4-Flash engine as its own component under components/shapes/hy4/engine/
# (strata_control/shape_engine.py: a shape engine's place is <components>/shapes/
# <shape>/engine/<package>/, beside the Strata engine's components/engine/ and
# never inside it; --shape hy4 names the program strata-hy4, skips the picture
# reader and the hipBLASLt checks, and writes "shape": "hy4" into the manifest).
# It carries the same ROCm libraries as the engine, so no tuning table and no
# reader go with it.
mkdir -p /out/components/shapes
if [ "$hy4" = "ON" ]; then
  [ -x build/strata-hy4 ] || { echo "STRATA_BUILD_HY4=1 but build/strata-hy4 is missing" >&2; exit 1; }
  mkdir -p /stage-hy4 /out/components/shapes/hy4/engine
  cp build/strata-hy4 /stage-hy4/
  cat > /stage-hy4/BUILD.json <<JSON
{"version": "${version:-dev}", "source": "docker build", "archs": "$ROCM_ARCH", "shape": "hy4"}
JSON
  cat /stage-hy4/BUILD.json
  python3 tools/packaging/package_engine.py \
    --src /stage-hy4 --backend hip --arch "$ROCM_ARCH" --shape hy4 \
    --version "${version:-dev}" --variant "${ROCM_ARCH}-hy4" \
    --out /out/components/shapes/hy4/engine \
    --build-id "$(cat SOURCE_COMMIT 2>/dev/null || echo unknown)" \
    --allow-lib libhipblas.so.3 \
    --allow-lib libhipblaslt.so.1 \
    --allow-lib librocblas.so.5 \
    --allow-lib libamdhip64.so.7
fi
EOF_DOCKERFILE

############# Copy and install all #############
FROM rocm_base AS final

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      tini ca-certificates libgomp1 libatomic1 python3 python3-venv \
      libdrm2 libdrm-amdgpu1 libelf1t64 libtinfo6 libpci3 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=files_strata /src/terminal /opt/strata/terminal
COPY --from=build_strata /out/components/engine/ /opt/strata/components/engine/
COPY --from=build_strata /out/components/shapes/ /opt/strata/components/shapes/
COPY --from=files_strata /src/tools/docker/entrypoint.sh /opt/strata/entrypoint.sh
COPY --from=files_strata /src/tools/docker/healthcheck.sh /opt/strata/healthcheck.sh
COPY --from=files_strata /src/tools/docker/strata-wrapper.sh /usr/local/bin/strata
RUN chmod 0755 /opt/strata/entrypoint.sh /opt/strata/healthcheck.sh /usr/local/bin/strata

# The Terminal's private runtime: upstream ships a pinned CPython in the release
# archive, here a venv with the same pins of terminal/requirements*.txt.
RUN set -eux; \
    cd /opt/strata/terminal; \
    python3 -m venv python; \
    python/bin/pip install --no-cache-dir -r requirements.txt -r requirements-monitor.txt; \
    bin/strata --version

# The component manifest hashes, every library of the programs resolves against
# the package or the base image's ROCm, and the programs start: the engine's
# picture reader (the one this image was built with), and strata-hy4 where the
# package is the Hy4-Flash shape component (components/shapes/hy4/engine/),
# which carries no reader by design.
RUN set -e; \
    for d in /opt/strata/components/engine/*/ /opt/strata/components/shapes/*/engine/*/; do \
      [ -d "$d" ] || continue; \
      echo "== $d"; \
      PYTHONPATH=/opt/strata/terminal /opt/strata/terminal/python/bin/python3 -c 'import sys; from pathlib import Path; from strata_control import engine_component as ec; ec.verify(ec.read_manifest_any(Path(sys.argv[1])), full=True)' "$d"; \
      readers=0; hy4=0; \
      for f in "$d"strata "$d"strata-hy4 "$d"strata-vision "$d"strata-vision-hip; do \
        [ -f "$f" ] || continue; \
        miss=$(LD_LIBRARY_PATH="$d:/opt/rocm/lib" ldd "$f" 2>/dev/null | grep 'not found' | grep -v -E 'libcuda\.so|libnvidia|libhsa-runtime64|libdrm_amdgpu' || true); \
        if [ -n "$miss" ]; then echo "MISSING LIBS in $f"; echo "$miss"; exit 1; fi; \
        case "${f##*/}" in strata-vision|strata-vision-hip) readers=$((readers + 1)); "$f" --version;; strata-hy4) hy4=1; "$f" --version;; esac; \
      done; \
      if [ "$hy4" = "1" ]; then echo "libraries of $d resolve inside this image, and strata-hy4 starts"; continue; fi; \
      if [ "$readers" -lt 1 ]; then echo "no picture reader in $d: this image was built without one"; exit 1; fi; \
      echo "libraries of $d resolve inside this image, and its picture reader starts"; \
    done

WORKDIR /opt/strata
ENV STRATA_COMPONENTS_DIR=/opt/strata/components \
    STRATA_INSTALL_DIR=/data/install \
    XDG_STATE_HOME=/data/state \
    XDG_CONFIG_HOME=/data/config \
    HOME=/data/home \
    PORT=8080 \
    LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONNOUSERSITE=1 \
    STRATA_IN_DOCKER=1

VOLUME ["/data"]
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=8s --start-period=2h --retries=3 CMD ["/opt/strata/healthcheck.sh"]
STOPSIGNAL SIGTERM
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/strata/entrypoint.sh"]
CMD ["run"]
