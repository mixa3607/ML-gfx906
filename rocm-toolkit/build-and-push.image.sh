#!/bin/bash
set -eo pipefail

cd $(dirname $0)
source ../env.sh "rocm" "rocm-toolkit"

BASE_ROCM_IMAGE="${ROCM_IMAGE}:${ROCM_VERSION}-complete"
if [ "$ROCM_TOOLKIT_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "$ROCM_TOOLKIT_IMAGE:${ROCM_VERSION}-${REPO_GIT_REF}"
    "$ROCM_TOOLKIT_IMAGE:${ROCM_VERSION}"
  )
else
  IMAGE_TAGS=(
    "$ROCM_TOOLKIT_IMAGE:${ROCM_VERSION}-${REPO_GIT_REF}-pre"
  )
fi

declare -A IMAGE_ANNOTATIONS
IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/rocm-toolkit"
IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="ROCm gfx906 toolkit"
IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${BASE_ROCM_IMAGE}"

echo "Start building ROCm toolkit image..."
echo "ROCm base image: ${BASE_ROCM_IMAGE}"
echo "ROCm version:    ${ROCM_VERSION}"
echo "Is release:      ${ROCM_TOOLKIT_IS_RELEASE}"
echo "Push:            ${ROCM_TOOLKIT_PUSH}"

DOCKER_EXTRA_ARGS=()
for image_tag in "${IMAGE_TAGS[@]}"; do
  echo "Tag:             ${image_tag}"
  DOCKER_EXTRA_ARGS+=("--tag" "${image_tag}")
done
for key in "${!IMAGE_ANNOTATIONS[@]}"; do
  DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
done

if docker_image_pushed "${IMAGE_TAGS[0]}"; then
  echo -n "${IMAGE_TAGS[0]} already in registry. "
  if [ "$ROCM_TOOLKIT_FORCE_BUILD" == "1" ]; then
    echo "Force build..."
  else
    echo "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS+=(
  --build-arg "BASE_ROCM_IMAGE=${BASE_ROCM_IMAGE}"
  --build-arg "ROCM_VERSION=${ROCM_VERSION}"
  --progress plain
  --target final
  --file ./build-image.Dockerfile
  --pull
)

if [ "$ROCM_TOOLKIT_PUSH" == "1" ]; then
  DOCKER_EXTRA_ARGS+=(--push)
fi

mkdir -p ./logs
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" . 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
