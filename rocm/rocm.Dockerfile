ARG ROCM_BASE_IMAGE="docker.io/library/ubuntu:24.04"
ARG ROCM_ARCH="gfx906"
ARG THEROCK_VERSION="7.14"

############# Base image #############
FROM ${ROCM_BASE_IMAGE} AS rocm_base
ARG ROCM_ARCH
ARG THEROCK_VERSION
RUN --mount=type=bind,src=/,target=/build-context \
    apt-get update && apt-get install -y ca-certificates curl git && \
    /build-context/setup-apt-gfx906.sh && \
    apt-get update && apt-get install -y $(apt-cache pkgnames amdrocm | grep -E "${THEROCK_VERSION}(|-${ROCM_ARCH})\$") && \
    rm -rf /var/lib/{apt,dpkg,cache,log}/ && \
    true

############# Final image #############
FROM rocm_base AS final
