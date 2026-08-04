ARG ROCM_BASE_IMAGE="docker.io/library/ubuntu:24.04"
ARG ROCM_BUILD="7.14.0-gfx906+20260802001858"

############# Base image #############
FROM ${ROCM_BASE_IMAGE} AS rocm_base
ARG ROCM_BUILD

ENV ROCM_BUILD=$ROCM_BUILD
ENV ROCM_PATH=/opt/rocm
ENV PATH=/opt/rocm/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

RUN --mount=type=bind,src=/,target=/build-context <<EOF_DOCKERFILE bash
set -eo pipefail

apt-get update
apt-get install --no-install-recommends -y ca-certificates curl git jq
/build-context/install-gfx906-repo.sh

apt-get update
/build-context/install-gfx906-rocm.sh

rm -rf /var/lib/apt/lists/*
EOF_DOCKERFILE

############# Final image #############
FROM rocm_base AS final
