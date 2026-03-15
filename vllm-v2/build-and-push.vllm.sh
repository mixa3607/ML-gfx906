#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh "pytorch" "vllm-v2"

IMAGE_TAGS=(
  "${VLLM_IMAGE}:${VLLM_PRESET_NAME}-${REPO_GIT_REF}"
  "${VLLM_IMAGE}:${VLLM_PRESET_NAME}"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  DOCKER_EXTRA_ARGS+=("-t" "${IMAGE_TAGS[$i]}")
done

mkdir -p ./logs
docker buildx build ${DOCKER_EXTRA_ARGS[@]} --push \
  --build-arg BASE_PYTORCH_IMAGE=${TORCH_IMAGE}:${VLLM_PYTORCH_VERSION}-rocm-${VLLM_ROCM_VERSION} \
  --build-arg MAX_JOBS="${VLLM_MAX_JOBS}" \
  \
  --build-arg VLLM_REPO=${VLLM_REPO}     \
  --build-arg VLLM_BRANCH=${VLLM_BRANCH} \
  --build-arg VLLM_COMMIT=${VLLM_COMMIT} \
  --build-arg VLLM_PATCH=${VLLM_PATCH}   \
  \
  --build-arg FA_REPO=${VLLM_FA_REPO}     \
  --build-arg FA_BRANCH=${VLLM_FA_BRANCH} \
  --build-arg FA_COMMIT=${VLLM_FA_COMMIT} \
  --build-arg FA_PATCH=${VLLM_FA_PATCH}   \
  \
  --build-arg TRITON_REPO=${VLLM_TRITON_REPO}     \
  --build-arg TRITON_BRANCH=${VLLM_TRITON_BRANCH} \
  --build-arg TRITON_COMMIT=${VLLM_TRITON_COMMIT} \
  --build-arg TRITON_PATCH=${VLLM_TRITON_PATCH}   \
  \
  --progress=plain --target final -f ./vllm.Dockerfile ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
