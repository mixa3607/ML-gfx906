#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$VLLM_IMAGE:${VLLM_PRESET_NAME}-${REPO_GIT_REF}"
  "$VLLM_IMAGE:${VLLM_PRESET_NAME}"
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
  --build-arg BASE_PYTORCH_IMAGE=$TORCH_IMAGE:${VLLM_PYTORCH_VERSION}-rocm-${VLLM_ROCM_VERSION} \
  --build-arg VLLM_BRANCH=$VLLM_BRANCH \
  --build-arg TRITON_BRANCH=$VLLM_TRITON_BRANCH \
  --progress=plain --target final -f ./vllm.Dockerfile ./submodules 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
