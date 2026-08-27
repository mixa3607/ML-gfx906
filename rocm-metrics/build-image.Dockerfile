ARG BASE_IMAGE="docker.io/library/ubuntu:24.04"
ARG PACKAGE_SOURCE=context

FROM ${BASE_IMAGE} AS packages-source
ARG PACKAGE_SOURCE

RUN --mount=type=bind,from=packages,target=/packages-src <<'EOF_PACKAGES' bash
set -eo pipefail

mkdir -p /packages
if [ "$PACKAGE_SOURCE" = "context" ]; then
  cp /packages-src/*.deb /packages/
elif [ "$PACKAGE_SOURCE" = "apt" ]; then
  echo "APT package source is not implemented" >&2
  exit 1
else
  echo "Unsupported PACKAGE_SOURCE=$PACKAGE_SOURCE" >&2
  exit 1
fi
EOF_PACKAGES

FROM ${BASE_IMAGE} AS final
RUN --mount=type=bind,from=packages-source,source=/packages,target=/packages <<'EOF_INSTALL' bash
set -eo pipefail
dpkg -i /packages/*.deb
EOF_INSTALL

EXPOSE 9487
CMD ["/usr/bin/vega20-metrics", "--listen", ":9487", "--register-backend", "debugfs"]
