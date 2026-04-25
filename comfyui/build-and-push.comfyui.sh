#/bin/bash
set -e
set -o pipefail

cd $(dirname $0)
source ../env.sh "comfyui"

IMAGE_TAGS=(
  "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-cuda-${COMFYUI_CUDA_VERSION}"
  "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-cuda-${COMFYUI_CUDA_VERSION}-${REPO_GIT_REF}"
  "$COMFYUI_IMAGE:${COMFYUI_BRANCH}-torch-${COMFYUI_PYTORCH_VERSION}-cuda-${COMFYUI_CUDA_VERSION}-${REPO_GIT_REF}"
  "$COMFYUI_IMAGE:latest-cuda-${COMFYUI_CUDA_VERSION}"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo -n "${IMAGE_TAGS[0]} already in registry. "
  if [ "$COMFYUI_FORCE_BUILD" == "1" ]; then
    echo "Force build."
  else
    echo "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  DOCKER_EXTRA_ARGS+=("-t" "${IMAGE_TAGS[$i]}")
done

mkdir ./logs || true
docker buildx build ${DOCKER_EXTRA_ARGS[@]} --push \
  --build-arg BASE_PYTORCH_IMAGE=${COMFYUI_TORCH_IMAGE}:${COMFYUI_PYTORCH_VERSION}-cuda${COMFYUI_CUDA_VERSION}-runtime \
  --build-arg COMFY_REPO=$COMFYUI_REPO \
  --build-arg COMFY_BRANCH=$COMFYUI_BRANCH \
  --build-arg COMFY_COMMIT=$COMFYUI_COMMIT \
  --progress=plain --target final -f ./comfyui.Dockerfile --push ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
