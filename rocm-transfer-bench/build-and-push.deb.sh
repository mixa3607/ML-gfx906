#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_VERSION:="7.14"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${TB_VERSION:="main"}"
: "${TB_PUSH:="0"}"
: "${TB_VERSION_SUFFIX:="${ROCM_VERSION}+${ROCM_ARCH}+${REPO_GIT_REF}"}"
: "${TB_BASE_IMAGE:="${ROCM_IMAGE}:${ROCM_VERSION}-complete"}"
: "${TB_PACKAGES_DIR:="$PWD/output/rocm${ROCM_VERSION}/tb-${TB_VERSION}-${TB_VERSION_SUFFIX}"}"

print INFO "Start building TransferBench deb package..."
print INFO "TB VERSION:        ${TB_VERSION}"
print INFO "TB VERSION SUFFIX: ${TB_VERSION_SUFFIX}"
print INFO "TB PACKAGES DIR:   ${TB_PACKAGES_DIR}"
print INFO "ROCM IMAGE:        ${TB_BASE_IMAGE}"
print INFO "ROCM ARCH:         ${ROCM_ARCH}"
print INFO "ROCM VERSION:      ${ROCM_VERSION}"
print INFO "PUSH:              ${TB_PUSH}"

if [ -d "$TB_PACKAGES_DIR" ]; then
  print INFO "Directory $TB_PACKAGES_DIR exist. "
  if [ "$TB_FORCE_BUILD" == "1" ]; then
    print WARN "Force build..."
  else
    print WARN "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS=(
  --build-arg "BASE_ROCM_IMAGE=${TB_BASE_IMAGE}"
  --build-arg "ROCM_ARCH=${ROCM_ARCH}"
  --build-arg "ROCM_VERSION=${ROCM_VERSION}"
  --build-arg "VERSION_SUFFIX=${TB_VERSION_SUFFIX}"
  --build-arg "TB_BRANCH=${TB_VERSION}"
  --progress plain
  --pull
  --target final 
  --file ./build-deb.Dockerfile
  --output "type=local,dest=$TB_PACKAGES_DIR"
)

mkdir -p ./logs || true
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log

# Push packages
if [ "$TB_PUSH" == "1" ]; then
  POD_DST="rocm-build/aptly-0:/root/packages/rocm-transfer-bench"
  find "$TB_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" | xargs -I {} kubectl cp {} "$POD_DST"
fi
