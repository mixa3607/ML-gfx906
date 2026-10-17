#!/bin/bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_VERSION:="7.14"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${RBT_VERSION:="develop"}"
: "${RBT_PUSH:="0"}"
: "${RBT_VERSION_SUFFIX:="${ROCM_VERSION}+${ROCM_ARCH}+${REPO_GIT_REF}"}"
: "${RBT_BASE_IMAGE:="${ROCM_IMAGE}:${ROCM_VERSION}-complete"}"
: "${RBT_PACKAGES_DIR:="$PWD/output/rocm${ROCM_VERSION}/rbt-${RBT_VERSION}-${RBT_VERSION_SUFFIX}"}"

print INFO "Start building ROCm Bandwidth Test deb package..."
print INFO "RBT VERSION:        ${RBT_VERSION}"
print INFO "RBT VERSION SUFFIX: ${RBT_VERSION_SUFFIX}"
print INFO "RBT PACKAGES DIR:   ${RBT_PACKAGES_DIR}"
print INFO "ROCM IMAGE:         ${RBT_BASE_IMAGE}"
print INFO "ROCM ARCH:          ${ROCM_ARCH}"
print INFO "ROCM VERSION:       ${ROCM_VERSION}"
print INFO "PUSH:               ${RBT_PUSH}"

if [ -d "$RBT_PACKAGES_DIR" ]; then
  print INFO "Directory $RBT_PACKAGES_DIR exists."
  if [ "$RBT_FORCE_BUILD" != "1" ]; then
    print WARN "Skip."
    exit 0
  fi
  print WARN "Force build..."
fi

DOCKER_EXTRA_ARGS=(
  --build-arg "BASE_ROCM_IMAGE=${RBT_BASE_IMAGE}"
  --build-arg "ROCM_ARCH=${ROCM_ARCH}"
  --build-arg "ROCM_VERSION=${ROCM_VERSION}"
  --build-arg "VERSION_SUFFIX=${RBT_VERSION_SUFFIX}"
  --build-arg "RBT_BRANCH=${RBT_VERSION}"
  --progress plain
  --pull
  --target final
  --file ./build-deb.Dockerfile
  --output "type=local,dest=$RBT_PACKAGES_DIR"
)

mkdir -p ./logs
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"

if [ "$RBT_PUSH" = "1" ]; then
  SCP_DST="k3s@kube-worker6.arkprojects.lan:/home/k3s/rocm-dev-packages/rocm-bandwidth-test"
  find "$RBT_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" -exec scp {} "$SCP_DST" \;
fi
