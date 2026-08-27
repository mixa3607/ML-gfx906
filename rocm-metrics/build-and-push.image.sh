#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../env.sh "rocm-metrics" "rocm"

METRICS_VERSION_SUFFIX="${ROCM_VERSION}+${ROCM_ARCH}+${REPO_GIT_REF}"
METRICS_PACKAGE_VERSION="${METRICS_VERSION}+${METRICS_VERSION_SUFFIX}"
METRICS_PACKAGES_DIR="$PWD/output/rocm${ROCM_VERSION}/rocm-metrics-${METRICS_PACKAGE_VERSION}"
IMAGE_TAGS=(
  "${METRICS_IMAGE}:${METRICS_VERSION}-rocm-${ROCM_VERSION}-${REPO_GIT_REF}"
  "${METRICS_IMAGE}:${METRICS_VERSION}-rocm-${ROCM_VERSION}"
)

if docker_image_pushed "${IMAGE_TAGS[0]}" && [ "${METRICS_FORCE_BUILD:-}" != "1" ]; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip."
  exit 0
fi

DOCKER_EXTRA_ARGS=(
  --build-arg "PACKAGE_SOURCE=${METRICS_PACKAGES_SOURCE}"
  --progress plain
  --pull
  --target final
  --file ./build-image.Dockerfile
)
for tag in "${IMAGE_TAGS[@]}"; do
  DOCKER_EXTRA_ARGS+=(--tag "$tag")
done

if [ "$METRICS_PACKAGES_SOURCE" = "context" ]; then
  if [ ! -d "$METRICS_PACKAGES_DIR" ]; then
    echo "$METRICS_PACKAGES_DIR does not exist. Build the deb first."
    exit 1
  fi
  DOCKER_EXTRA_ARGS+=(--build-context "packages=${METRICS_PACKAGES_DIR}")
elif [ "$METRICS_PACKAGES_SOURCE" = "apt" ]; then
  DOCKER_EXTRA_ARGS+=(--build-context "packages=$(mktemp -d)")
else
  echo "Unsupported METRICS_PACKAGES_SOURCE=$METRICS_PACKAGES_SOURCE" >&2
  exit 1
fi

if [ "$METRICS_PUSH" = "1" ]; then
  DOCKER_EXTRA_ARGS+=(--push)
fi

mkdir -p ./logs
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build-image_$(date +%Y%m%d%H%M%S).log"
