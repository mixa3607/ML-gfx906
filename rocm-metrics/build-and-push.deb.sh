#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../env.sh "rocm-metrics" "rocm"

METRICS_VERSION_SUFFIX="${ROCM_VERSION}+${ROCM_ARCH}+${REPO_GIT_REF}"
METRICS_PACKAGE_VERSION="${METRICS_VERSION}+${METRICS_VERSION_SUFFIX}"
METRICS_PACKAGES_DIR="$PWD/output/rocm${ROCM_VERSION}/rocm-metrics-${METRICS_PACKAGE_VERSION}"

echo "Start building rocm-metrics deb package..."
echo "METRICS VERSION:      ${METRICS_VERSION}"
echo "PACKAGE VERSION:      ${METRICS_PACKAGE_VERSION}"
echo "PACKAGES DIR:         ${METRICS_PACKAGES_DIR}"
echo "PUSH:                 ${METRICS_PUSH}"

if [ -d "$METRICS_PACKAGES_DIR" ] && [ "${METRICS_FORCE_BUILD:-}" != "1" ]; then
  echo "Directory $METRICS_PACKAGES_DIR exists. Skip."
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
  SCP_DST="k3s@kube-worker6.arkprojects.lan:/home/k3s/rocm-dev-packages/rocm-metrics"
  scp "$METRICS_PACKAGES_DIR"/*.deb "$METRICS_PACKAGES_DIR/index.txt" "$SCP_DST"
fi
