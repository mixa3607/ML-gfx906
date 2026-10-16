ARG ROCM_IMAGE="docker.io/mixa3607/rocm-gfx906:7.14-complete"

ARG STRATA_REPO="https://github.com/Niko1221/Strata.git"
ARG STRATA_BRANCH="v0.1.41"
ARG STRATA_COMMIT=""
ARG STRATA_PATCH="gfx906-setup.patch"

############# Base image #############
FROM ${ROCM_IMAGE} AS rocm_base

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bash \
      build-essential \
      ca-certificates \
      cmake \
      curl \
      git \
      libatomic1 \
      libgomp1 \
      ninja-build \
      pkg-config \
      python3 \
      python3-dev \
      python3-pip \
      python3-venv \
      unzip && \
    rm -rf /var/lib/apt/lists/*

############# Clone Strata #############
FROM rocm_base AS files_strata
ARG STRATA_REPO
ARG STRATA_BRANCH
ARG STRATA_COMMIT
ARG STRATA_PATCH

WORKDIR /opt/strata
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
chmod +x docker-entrypoint.sh setup.sh
EOF_DOCKERFILE

############# Build the gfx906 engine #############
FROM rocm_base AS final
WORKDIR /opt/strata

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    STRATA_EXECV=1 \
    ROCM_PATH=/opt/rocm \
    HIP_PATH=/opt/rocm \
    HIP_PLATFORM=amd \
    HIP_COMPILER=clang \
    HIP_RUNTIME=rocclr \
    HSA_OVERRIDE_GFX_VERSION=9.0.6 \
    LD_LIBRARY_PATH=/opt/rocm/lib

COPY --from=files_strata /opt/strata /opt/strata

RUN python3 -m venv .venv \
    && .venv/bin/pip install --no-cache-dir --upgrade pip \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

# extra/build-gfx906.py downloads the pinned llama.cpp commit, then runs the
# same gfx906 cmake recipe as a known-good local image build.
COPY extra/build-gfx906.py /tmp/build-gfx906.py
RUN .venv/bin/python /tmp/build-gfx906.py \
    && rm -f /tmp/build-gfx906.py \
    && test -x /opt/strata/engine/strata \
    && test -f /opt/strata/engine/BUILD.json

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=600s --retries=3 \
  CMD curl -fs "http://127.0.0.1:${PORT:-8080}/health" || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
