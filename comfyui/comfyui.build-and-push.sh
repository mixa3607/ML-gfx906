#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

echo | docker buildx build --builder=remote \
  --build-arg BASE_ROCM_IMAGE=$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-${REPO_GIT_REF}-complete \
  --build-arg BASE_COMFY_IMAGE=$BASE_UBUNTU_REGISTRY/ubuntu:24.04 \
  -t $PATCHED_COMFYUI_REGISTRY/comfyui:${COMFYUI_GIT_REF}-rocm-${ROCM_VERSION}-patch-${REPO_GIT_REF} \
  -t $PATCHED_COMFYUI_REGISTRY/comfyui:${COMFYUI_GIT_REF}-rocm-${ROCM_VERSION} \
  --target final -f ./comfyui.Dockerfile --push --progress=plain ./submodules/ComfyUI
