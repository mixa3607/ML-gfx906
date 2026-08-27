ARG BASE_IMAGE="docker.io/library/debian:bookworm-slim"
ARG PACKAGE_SOURCE=context
ARG PACKAGES_BASE_URL=""

FROM ${BASE_IMAGE} AS packages-source
ARG PACKAGE_SOURCE
ARG PACKAGES_BASE_URL

RUN --mount=type=bind,from=packages,target=/packages-src <<'EOF_PACKAGES' bash
set -eo pipefail

mkdir -p /packages
if [ "$PACKAGE_SOURCE" = "context" ]; then
  cp /packages-src/*.deb /packages/
elif [ "$PACKAGE_SOURCE" = "fetch" ]; then
  apt-get update
  apt-get install -y --no-install-recommends ca-certificates curl
  curl --fail --output /packages/index.txt "${PACKAGES_BASE_URL}/index.txt"
  while read -r package; do
    curl --fail --output "/packages/${package}" "${PACKAGES_BASE_URL}/${package}"
  done < /packages/index.txt
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
