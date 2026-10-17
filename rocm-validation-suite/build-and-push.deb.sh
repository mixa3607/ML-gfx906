#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_VERSION:="7.14"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${RVS_VERSION:="main"}"
: "${RVS_PUSH:="0"}"
: "${RVS_VERSION_SUFFIX:="${ROCM_VERSION}+${ROCM_ARCH}+${REPO_GIT_REF}"}"
: "${RVS_BASE_IMAGE:="${ROCM_IMAGE}:${ROCM_VERSION}-complete"}"
: "${RVS_PACKAGES_DIR:="$PWD/output/rocm${ROCM_VERSION}/rvs-${RVS_VERSION}-${RVS_VERSION_SUFFIX}"}"

print INFO "Start building ROCm Validation Suite deb package..."
print INFO "RVS VERSION:        ${RVS_VERSION}"
print INFO "RVS VERSION SUFFIX: ${RVS_VERSION_SUFFIX}"
print INFO "RVS PACKAGES DIR:   ${RVS_PACKAGES_DIR}"
print INFO "ROCM IMAGE:         ${RVS_BASE_IMAGE}"
print INFO "ROCM ARCH:          ${ROCM_ARCH}"
print INFO "ROCM VERSION:       ${ROCM_VERSION}"
print INFO "PUSH:               ${RVS_PUSH}"

if [ -d "$RVS_PACKAGES_DIR" ]; then
  print INFO "Directory $RVS_PACKAGES_DIR exist. "
  if [ "$RVS_FORCE_BUILD" == "1" ]; then
    print WARN "Force build..."
  else
    print WARN "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS=(
  --build-arg "BASE_ROCM_IMAGE=${RVS_BASE_IMAGE}"
  --build-arg "VERSION_SUFFIX=${RVS_VERSION_SUFFIX}"
  --build-arg "RVS_BRANCH=${RVS_VERSION}"
  --progress plain
  --pull
  --target final 
  --file ./build-deb.Dockerfile
  --output "type=local,dest=$RVS_PACKAGES_DIR"
)

mkdir -p ./logs || true
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log

# Push packages
if [ "$RVS_PUSH" == "1" ]; then
  SCP_DST="k3s@kube-worker6.arkprojects.lan:/home/k3s/rocm-dev-packages/rocm-validation-suite"
  find "$RVS_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" | xargs -I {} scp {} "$SCP_DST" 
fi
