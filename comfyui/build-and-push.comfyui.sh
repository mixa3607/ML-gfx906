#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$COMFYUI_IMAGE:${COMFYUI_GIT_REF}-rocm-${COMFYUI_ROCM_VERSION}-patch-${REPO_GIT_REF}"
  "$COMFYUI_IMAGE:${COMFYUI_GIT_REF}-rocm-${COMFYUI_ROCM_VERSION}"
  "$COMFYUI_IMAGE:latest-rocm-${COMFYUI_ROCM_VERSION}"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  DOCKER_EXTRA_ARGS+=("-t" "${IMAGE_TAGS[$i]}")
done

mkdir ./logs || true
docker buildx build ${DOCKER_EXTRA_ARGS[@]} --push \
  --build-arg BASE_ROCM_IMAGE=$PATCHED_ROCM_IMAGE:${COMFYUI_ROCM_VERSION}-complete \
  --build-arg BASE_COMFY_IMAGE=$COMFYUI_BASE_IMAGE \
  --progress=plain --target final -f ./comfyui.Dockerfile --push ./submodules/ComfyUI 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
