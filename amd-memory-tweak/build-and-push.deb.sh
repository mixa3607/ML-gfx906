#!/bin/bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${AMT_VERSION:="0.0.0"}"
: "${AMT_PUSH:="0"}"
: "${AMT_BASE_IMAGE:="docker.io/library/ubuntu:24.04"}"
: "${AMT_VERSION_SUFFIX:="gfx906+${REPO_GIT_REF}"}"
: "${AMT_PACKAGES_DIR:="$PWD/output/amt-${AMT_VERSION}-${AMT_VERSION_SUFFIX}"}"

print INFO "Start building AMD Memory Tweak deb package..."
print INFO "AMT VERSION:        ${AMT_VERSION}"
print INFO "AMT VERSION SUFFIX: ${AMT_VERSION_SUFFIX}"
print INFO "AMT PACKAGES DIR:   ${AMT_PACKAGES_DIR}"
print INFO "BASE IMAGE:         ${AMT_BASE_IMAGE}"
print INFO "PUSH:               ${AMT_PUSH}"

if [ -d "$AMT_PACKAGES_DIR" ]; then
  print INFO "Directory $AMT_PACKAGES_DIR exists."
  if [ "${AMT_FORCE_BUILD:-0}" = "1" ]; then
    print WARN "Force build..."
  else
    print WARN "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS=(
  --build-arg "BASE_UBUNTU_IMAGE=${AMT_BASE_IMAGE}"
  --build-arg "AMT_VERSION=${AMT_VERSION}"
  --build-arg "VERSION_SUFFIX=${AMT_VERSION_SUFFIX}"
  --progress plain
  --pull
  --target final
  --file ./build-deb.Dockerfile
  --output "type=local,dest=$AMT_PACKAGES_DIR"
)

mkdir -p ./logs
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context \
  2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"

if [ "$AMT_PUSH" = "1" ]; then
  SCP_DST="k3s@kube-worker6.arkprojects.lan:/home/k3s/rocm-dev-packages/amd-memory-tweak"
  find "$AMT_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" -exec scp {} "$SCP_DST" \;
fi
