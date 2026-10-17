#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${METRICS_VERSION:="0.1.0"}"
: "${METRICS_PUSH:="1"}"

METRICS_VERSION_SUFFIX="${REPO_GIT_REF}"
METRICS_PACKAGE_VERSION="${METRICS_VERSION}+${METRICS_VERSION_SUFFIX}"
METRICS_PACKAGES_DIR="$PWD/output/vega20-metrics-exporter-${METRICS_PACKAGE_VERSION}"

print INFO "Start building vega20-metrics-exporter deb package..."
print INFO "METRICS VERSION:      ${METRICS_VERSION}"
print INFO "PACKAGE VERSION:      ${METRICS_PACKAGE_VERSION}"
print INFO "PACKAGES DIR:         ${METRICS_PACKAGES_DIR}"
print INFO "PUSH:                 ${METRICS_PUSH}"

if [ -d "$METRICS_PACKAGES_DIR" ] && [ "${METRICS_FORCE_BUILD:-}" != "1" ]; then
  print WARN "Directory $METRICS_PACKAGES_DIR exists. Skip."
  exit 0
fi

mkdir -p ./logs
docker buildx build \
  --build-arg "PACKAGE_VERSION=${METRICS_PACKAGE_VERSION}" \
  --progress plain \
  --pull \
  --target final \
  --file ./build-deb.Dockerfile \
  --output "type=local,dest=${METRICS_PACKAGES_DIR}" \
  ./build-context 2>&1 | tee "./logs/build-deb_$(date +%Y%m%d%H%M%S).log"

find "$METRICS_PACKAGES_DIR" -maxdepth 1 -type f -name '*.deb' -printf '%f\n' | sort > "$METRICS_PACKAGES_DIR/index.txt"

if [ "$METRICS_PUSH" = "1" ]; then
  SCP_DST="k3s@kube-worker6.arkprojects.lan:/home/k3s/rocm-dev-packages/vega20-metrics-exporter"
  find "$METRICS_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" -exec scp {} "$SCP_DST" \;
fi
