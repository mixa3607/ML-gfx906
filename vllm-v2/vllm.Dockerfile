# Build seq: rocm_base => build_base => {build_triton => build_fa => build_vllm, build_rust} => final

ARG BASE_PYTORCH_IMAGE="docker.io/mixa3607/pytorch-gfx906:v2.10.0-rocm-6.3.3"
ARG MAX_JOBS=""
ARG EXTRA_REQUIREMENTS="empty.txt"
# Optional apt mirror override (e.g. http://ubuntu.mirror.lrz.de/ubuntu/).
# Empty = keep the image default. Rewrites both archive. and security. hosts.
ARG APT_MIRROR=""

ARG VLLM_REPO="https://github.com/ai-infos/vllm-gfx906-mobydick.git"
ARG VLLM_BRANCH="main"
ARG VLLM_COMMIT=""
ARG VLLM_PATCH="empty.patch"
ARG VLLM_VERSION=""

ARG TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"
ARG TRITON_BRANCH="main"
ARG TRITON_COMMIT=""
ARG TRITON_PATCH="empty.patch"

ARG FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"
ARG FA_BRANCH="main"
ARG FA_COMMIT=""
ARG FA_PATCH="empty.patch"

############# Base image #############
FROM ${BASE_PYTORCH_IMAGE} AS rocm_base
ARG APT_MIRROR
# Swap in a faster/regional mirror when requested (no-op by default).
RUN if [ -n "$APT_MIRROR" ]; then \
      sed -i "s|http://archive.ubuntu.com/ubuntu/|$APT_MIRROR|g; s|http://security.ubuntu.com/ubuntu/|$APT_MIRROR|g" \
        /etc/apt/sources.list.d/ubuntu.sources; \
    fi

# Set environment variables
ENV ROCM_ARCH=gfx906
ENV PYTORCH_ROCM_ARCH=gfx906
ENV LD_LIBRARY_PATH=/opt/rocm/lib:/usr/local/lib:
ENV VLLM_TARGET_DEVICE=rocm
ENV FLASH_ATTENTION_TRITON_AMD_AUTOTUNE=0
ENV FLASH_ATTENTION_TRITON_AMD_ENABLE=TRUE

# Install base tools
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install --upgrade --ignore-installed '/opt/rocm/share/amd_smi' pyjwt && \
    apt-get update && apt-get install curl git wget jq aria2 -y

############# Clone repos #############
FROM rocm_base AS files_triton
ARG TRITON_REPO
ARG TRITON_BRANCH
ARG TRITON_COMMIT
ARG TRITON_PATCH
# Clone
WORKDIR /app/triton
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${TRITON_BRANCH} ${TRITON_REPO} .
RUN if [ "$TRITON_COMMIT" != "" ]; then git checkout "$TRITON_COMMIT"; fi
# Patch
COPY ./patch/${TRITON_PATCH} ./${TRITON_PATCH}
RUN git apply ./${TRITON_PATCH} --allow-empty

FROM rocm_base AS files_fa
ARG FA_REPO
ARG FA_BRANCH
ARG FA_COMMIT
ARG FA_PATCH
# Clone
WORKDIR /app/flash-attention
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${FA_BRANCH} ${FA_REPO} .
RUN if [ "$FA_COMMIT" != "" ]; then git checkout "$FA_COMMIT"; fi
# Patch
COPY ./patch/${FA_PATCH} ./${FA_PATCH}
RUN git apply ./${FA_PATCH} --allow-empty

FROM rocm_base AS files_vllm
ARG VLLM_REPO
ARG VLLM_BRANCH
ARG VLLM_COMMIT
ARG VLLM_PATCH
ARG VLLM_VERSION
# Clone
WORKDIR /app/vllm
RUN git clone --depth 1 --recurse-submodules --shallow-submodules --jobs 4 --branch ${VLLM_BRANCH} ${VLLM_REPO} .
RUN if [ "$VLLM_COMMIT" != "" ]; then git checkout "$VLLM_COMMIT"; fi
# Tag this snapshot so setuptools-scm derives VLLM_VERSION (see AGENTS.md).
# Auto mode: fetch the declared tag; only synthesize it locally when the
# checkout is not already exactly tagged (shallow --branch clones fetch no
# tags, so untagged fork branches always take the synthetic tag, while a
# branch whose tip really is vX.Y.Z keeps its natural version). Set
# VLLM_VERSION="" in the preset to disable tagging entirely.
RUN if [ -n "$VLLM_VERSION" ]; then \
      git fetch --quiet --depth 1 origin "refs/tags/v${VLLM_VERSION}:refs/tags/v${VLLM_VERSION}" 2>/dev/null || true; \
      if ! git describe --tags --exact-match HEAD >/dev/null 2>&1; then \
        git tag -f "v${VLLM_VERSION}"; \
      fi; \
    fi
# Patch
COPY ./patch/${VLLM_PATCH} ./${VLLM_PATCH}
RUN git apply ./${VLLM_PATCH} --allow-empty

FROM rocm_base AS files_extra
ARG EXTRA_REQUIREMENTS
WORKDIR /app/extra-requirements
COPY ./requirements/${EXTRA_REQUIREMENTS} /app/extra-requirements/requirements.txt

############# Build base #############
FROM rocm_base AS build_base
# cmake/ninja are build tools the base image no longer ships (the TheRock-based
# v2.13.0-rocm-7.14 base is leaner than the older ROCm-SDK images).
RUN --mount=type=cache,target=/root/.cache/pip pip3 install build cmake ninja

############# Build Rust frontend (vllm-rs) #############
# vLLM 0.26+ ships a Rust component (the `vllm-rs` binary + `_rust_*` PyO3
# extensions) built via setuptools-rust. It is compiled here into precompiled
# artifacts that the wheel build stage reuses (see setup.py precompiled_build_rust),
# so the wheel stage does not need cargo/rustc/protoc. Mirrors upstream
# docker/Dockerfile.rocm's rust-toolchain + rust-build stages.
FROM build_base AS build_rust
ENV CARGO_HOME=/root/.cargo
ENV RUSTUP_HOME=/root/.rustup
ENV PATH=${CARGO_HOME}/bin:${PATH}
# Cap cargo parallelism (rustc easily hits RLIMIT_NOFILE / OOM otherwise).
ENV CARGO_BUILD_JOBS=4
ENV CARGO_NET_RETRY=10
ENV RUSTUP_MAX_RETRIES=10
WORKDIR /app/vllm
# --- Commit-independent inputs (stay layer-cached across vLLM commits) ---
# protoc is needed by tonic-build/prost-build. Vendored binary + well-known
# proto includes (same pinned version 34.2 and /usr/local layout as the fork's
# tools/install_protoc.sh) to avoid the flaky ubuntu mirrors in-build: distro
# protobuf-compiler is often too old for the Rust frontend's build.rs flags.
COPY ./protoc/ /usr/local/
COPY --from=files_vllm /app/vllm/requirements/build/rust.txt /tmp/rust.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip3 install -r /tmp/rust.txt && protoc --version
# --- Rust source inputs only: python-only commits do NOT invalidate this ---
COPY --from=files_vllm /app/vllm/rust ./rust
COPY --from=files_vllm /app/vllm/rust-toolchain.toml ./rust-toolchain.toml
COPY --from=files_vllm /app/vllm/tools/build_rust.py ./tools/build_rust.py
COPY --from=files_vllm /app/vllm/build_rust.sh ./build_rust.sh
RUN --mount=type=cache,target=/root/.cargo/registry,sharing=locked \
    --mount=type=cache,target=/root/.cargo/git,sharing=locked \
    --mount=type=cache,target=/root/.cargo/bin \
    --mount=type=cache,target=/root/.rustup \
    bash build_rust.sh && test -x vllm/vllm-rs

############# Build triton #############
FROM build_base AS build_triton
COPY --from=files_triton /app/triton /app/triton
WORKDIR /app/triton
RUN --mount=type=cache,target=/root/.cache/pip pip3 install -r python/requirements.txt
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    pip3 wheel -v --no-deps --no-build-isolation --wheel-dir /dist .
RUN --mount=type=cache,target=/root/.cache/pip pip3 install /dist/triton-*.whl
RUN ls /dist

############# Build FA #############
FROM build_triton AS build_fa
COPY --from=files_fa /app/flash-attention /app/flash-attention
WORKDIR /app/flash-attention
RUN --mount=type=cache,target=/root/.cache/pip pip3 install ninja packaging wheel pybind11 psutil
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    pip3 wheel -v --no-deps --no-build-isolation --wheel-dir /dist .
RUN --mount=type=cache,target=/root/.cache/pip pip3 install /dist/flash_attn-*.whl
RUN ls /dist

############# Build vllm #############
FROM build_fa AS build_vllm
# Commit-independent build deps first (layer-cached across vLLM commits).
# ROCm build deps the lean v2.13.0-rocm-7.14 base doesn't ship (older ROCm-SDK
# bases provided these): pkg-config (torch rocm_smi CMake lookup) and the
# libdrm/libnuma/libpci/liblzma dev packages (vllm CMake pkg-config lookups).
RUN apt-get update && apt-get install -y --no-install-recommends \
      pkg-config libdrm-dev libnuma-dev libpci-dev liblzma-dev \
 && rm -rf /var/lib/apt/lists/*
COPY --from=files_vllm /app/vllm /app/vllm
# Reuse the precompiled Rust artifacts so the wheel build skips cargo. setuptools-rust
# is still required at setup.py import time and is provided via requirements/rocm.txt.
COPY --from=build_rust /app/vllm/vllm/vllm-rs  /app/vllm/vllm/vllm-rs
COPY --from=build_rust /app/vllm/vllm/_rust_*.so /app/vllm/vllm/
WORKDIR /app/vllm
RUN --mount=type=cache,target=/root/.cache/pip pip3 install -r requirements/rocm.txt
# Build
ARG MAX_JOBS
RUN MAX_JOBS=${MAX_JOBS:-$(nproc)} \
    pip3 wheel -v --no-deps --no-build-isolation --wheel-dir /dist .
RUN --mount=type=cache,target=/root/.cache/pip pip3 install /dist/vllm-*.whl
RUN ls /dist 

############# Install all #############
FROM rocm_base AS final
WORKDIR /app/vllm
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,from=build_vllm,src=/app/vllm/requirements/,target=/app/vllm/requirements \
    --mount=type=bind,from=files_extra,src=/app/extra-requirements/,target=/app/extra-requirements \
    --mount=type=bind,from=build_vllm,src=/dist/,target=/dist \
    pip3 install /dist/*.whl /dist/flash_attn-*.whl -r /app/vllm/requirements/rocm.txt && \
    pip3 install -r /app/extra-requirements/*.txt && \
    true

CMD ["/bin/bash"]
