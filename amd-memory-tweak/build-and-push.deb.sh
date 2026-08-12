#!/bin/bash
set -eo pipefail

cd "$(dirname "$0")"
source ../env.sh "amd-memory-tweak"

AMT_VERSION_SUFFIX="gfx906+${REPO_GIT_REF}"
AMT_PACKAGES_DIR="$PWD/output/amt-${AMT_VERSION}-${AMT_VERSION_SUFFIX}"

echo "Start building AMD Memory Tweak deb package..."
echo "AMT VERSION:        ${AMT_VERSION}"
echo "AMT VERSION SUFFIX: ${AMT_VERSION_SUFFIX}"
echo "AMT PACKAGES DIR:   ${AMT_PACKAGES_DIR}"
echo "BASE IMAGE:         ${AMT_BASE_IMAGE}"
echo "PUSH:               ${AMT_PUSH}"

if [ -d "$AMT_PACKAGES_DIR" ]; then
  echo "Directory $AMT_PACKAGES_DIR exists."
  if [ "${AMT_FORCE_BUILD:-0}" = "1" ]; then
    echo "Force build..."
  else
    echo "Skip."
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
  find "$AMT_PACKAGES_DIR" -maxdepth 1 -mindepth 1 -name "*.deb" \
    -exec scp {} "$SCP_DST" \;
fi
