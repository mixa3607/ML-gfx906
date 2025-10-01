#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$PATCHED_COMFYUI_IMAGE:${COMFYUI_GIT_REF}-rocm-${COMFYUI_ROCM_VERSION}"
  "$PATCHED_COMFYUI_IMAGE:${COMFYUI_GIT_REF}-rocm-${COMFYUI_ROCM_VERSION}-patch-${REPO_GIT_REF}"
  "$PATCHED_COMFYUI_IMAGE:latest-rocm"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

docker buildx build ${IMAGE_TAGS[@]/#/-t } \
  --build-arg BASE_ROCM_IMAGE=$PATCHED_ROCM_IMAGE:${COMFYUI_ROCM_VERSION}-complete \
  --build-arg BASE_COMFY_IMAGE=$BASE_UBUNTU_REGISTRY/ubuntu:24.04 \
  --progress=plain --target final -f ./comfyui.Dockerfile --push ./submodules/ComfyUI
