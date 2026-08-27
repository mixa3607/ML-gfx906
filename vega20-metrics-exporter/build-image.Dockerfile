ARG BASE_IMAGE="docker.io/library/ubuntu:24.04"
ARG PACKAGE_SOURCE=context

FROM ${BASE_IMAGE} AS packages-source
ARG PACKAGE_SOURCE

RUN --mount=type=bind,from=packages,target=/packages-src \
    sh -ec 'case "$PACKAGE_SOURCE" in context) mkdir -p /packages; cp /packages-src/*.deb /packages/ ;; apt) echo "APT package source is not implemented" >&2; exit 1 ;; *) echo "Unsupported PACKAGE_SOURCE=$PACKAGE_SOURCE" >&2; exit 1 ;; esac'

FROM ${BASE_IMAGE} AS final
RUN --mount=type=bind,from=packages-source,source=/packages,target=/packages \
    dpkg -i /packages/*.deb

EXPOSE 9487
CMD ["/usr/bin/vega20-metrics"]
