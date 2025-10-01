#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

ROCM_VERSION=6.4.3
IMAGE_TAGS=(
  "$PATCHED_COMFYUI_REGISTRY/comfyui:${COMFYUI_GIT_REF}-rocm-${ROCM_VERSION}"
  "$PATCHED_COMFYUI_REGISTRY/comfyui:${COMFYUI_GIT_REF}-rocm-${ROCM_VERSION}-patch-${REPO_GIT_REF}"
  "$PATCHED_COMFYUI_REGISTRY/comfyui:latest-rocm"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

docker buildx build ${IMAGE_TAGS[@]/#/-t } \
  --build-arg BASE_ROCM_IMAGE=$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-complete \
  --build-arg BASE_COMFY_IMAGE=$BASE_UBUNTU_REGISTRY/ubuntu:24.04 \
  --progress=plain --target final -f ./comfyui.Dockerfile --push ./submodules/ComfyUI
