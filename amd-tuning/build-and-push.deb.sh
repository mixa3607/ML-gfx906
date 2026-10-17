#!/bin/bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${AMD_TUNING_VERSION:="0.0.0"}"
: "${AMD_TUNING_PUSH:="0"}"
: "${AMD_TUNING_BASE_IMAGE:="docker.io/library/ubuntu:24.04"}"
: "${AMD_TUNING_VERSION_SUFFIX:="gfx906+${REPO_GIT_REF}"}"
: "${AMD_TUNING_PACKAGES_DIR:="$PWD/output/amd-tuning-${AMD_TUNING_VERSION}-${AMD_TUNING_VERSION_SUFFIX}"}"

print INFO "Start building AMD tuning deb package..."
print INFO "AMD TUNING VERSION:        ${AMD_TUNING_VERSION}"
print INFO "AMD TUNING VERSION SUFFIX: ${AMD_TUNING_VERSION_SUFFIX}"
print INFO "AMD TUNING PACKAGES DIR:   ${AMD_TUNING_PACKAGES_DIR}"
print INFO "BASE IMAGE:                ${AMD_TUNING_BASE_IMAGE}"
print INFO "PUSH:                      ${AMD_TUNING_PUSH}"

if [ -d "$AMD_TUNING_PACKAGES_DIR" ]; then
  print INFO "Directory $AMD_TUNING_PACKAGES_DIR exists."
  if [ "${AMD_TUNING_FORCE_BUILD:-0}" = "1" ]; then
    print WARN "Force build..."
  else
    print WARN "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS=(
  --build-arg "BASE_UBUNTU_IMAGE=${AMD_TUNING_BASE_IMAGE}"
  --build-arg "AMD_TUNING_VERSION=${AMD_TUNING_VERSION}"
  --build-arg "VERSION_SUFFIX=${AMD_TUNING_VERSION_SUFFIX}"
  --progress plain
  --pull
  --target final
  --file ./build-deb.Dockerfile
  --output "type=local,dest=$AMD_TUNING_PACKAGES_DIR"
)

mkdir -p ./logs
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context \
  2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"

if [ "$AMD_TUNING_PUSH" = "1" ]; then
  SCP_DST="k3s@kube-worker6.arkprojects.lan:/home/k3s/rocm-dev-packages/amd-tuning"
  find "$AMD_TUNING_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" \
    -exec scp {} "$SCP_DST" \;
fi
