#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$TORCH_IMAGE:${TORCH_VERSION}-rocm-${TORCH_ROCM_VERSION}-${REPO_GIT_REF}"
  "$TORCH_IMAGE:${TORCH_VERSION}-rocm-${TORCH_ROCM_VERSION}"
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
  --build-arg BASE_ROCM_IMAGE="${PATCHED_ROCM_IMAGE}:${TORCH_ROCM_VERSION}-complete" \
  --build-arg ROCM_ARCH="${ROCM_ARCH}" \
  --build-arg PYTORCH_BRANCH=$TORCH_VERSION \
  --build-arg PYTORCH_VISION_BRANCH=$TORCH_VISION_VERSION \
  --target final -f ./torch.Dockerfile --progress=plain ./submodules 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
