#!/usr/bin/env bash
set -eo pipefail

cd $(dirname $0)
source ../env.sh "comfyui" "pytorch"

COMFYUI_BASE_IMAGE="${COMFYUI_TORCH_IMAGE}:v${COMFYUI_PYTORCH_VERSION}-rocm-${COMFYUI_ROCM_VERSION}"
if [ "$COMFYUI_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-torch-${COMFYUI_PYTORCH_VERSION}-rocm-${COMFYUI_ROCM_VERSION}-${REPO_GIT_REF}"
    "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-torch-${COMFYUI_PYTORCH_VERSION}-rocm-${COMFYUI_ROCM_VERSION}"
    "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-rocm-${COMFYUI_ROCM_VERSION}-${REPO_GIT_REF}"
    "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-rocm-${COMFYUI_ROCM_VERSION}"
    "$COMFYUI_IMAGE:latest-rocm-${COMFYUI_ROCM_VERSION}"
  )
else
  IMAGE_TAGS=(
    "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-torch-${COMFYUI_PYTORCH_VERSION}-rocm-${COMFYUI_ROCM_VERSION}-${REPO_GIT_REF}-pre"
  )
fi

declare -A IMAGE_ANNOTATIONS
IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/comfyui"
IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="ComfyUI gfx906"
IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${ROCM_BASE_IMAGE}"

echo "Start building ComfyUI image..."
echo "REPO:          ${COMFYUI_REPO}"
echo "VERSION:       ${COMFYUI_BRANCH}"
echo "COMMIT:        ${COMFYUI_COMMIT}"
echo "ROCM_VERSION:  ${COMFYUI_ROCM_VERSION}"
echo "TORCH_VERSION: ${COMFYUI_PYTORCH_VERSION}"
echo "IS_RELEASE:    ${COMFYUI_IS_RELEASE}"

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  echo "TAG:          ${IMAGE_TAGS[$i]}"
  DOCKER_EXTRA_ARGS+=("--tag" "${IMAGE_TAGS[$i]}")
done
for key in "${!IMAGE_ANNOTATIONS[@]}"; do
  echo "ANNOTATION:   ${key}: ${IMAGE_ANNOTATIONS[$key]}"
  DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
done

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo -n "${IMAGE_TAGS[0]} already in registry. "
  if [ "$COMFYUI_FORCE_BUILD" == "1" ]; then
    echo "Force build..."
  else
    echo "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS+=(
  --build-arg BASE_PYTORCH_IMAGE="${COMFYUI_BASE_IMAGE}"
  --build-arg COMFY_REPO="${COMFYUI_REPO}"
  --build-arg COMFY_BRANCH="${COMFYUI_BRANCH}"
  --build-arg COMFY_COMMIT="${COMFYUI_COMMIT}"
  --progress plain
  --target final 
  --file ./build-image.Dockerfile
  --pull
)

if [ "$COMFYUI_PUSH" == "1" ]; then
  DOCKER_EXTRA_ARGS+=(
    --push
  )
fi

mkdir -p ./logs || true
echo "Install ComfyUI to image"
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
