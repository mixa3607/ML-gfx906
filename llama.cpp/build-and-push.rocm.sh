#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh "llama.cpp" "rocm" 


IMAGE_TAGS=(
  "${LLAMA_IMAGE}:${LLAMA_PRESET_NAME}-${REPO_GIT_REF}"
  "${LLAMA_IMAGE}:${LLAMA_PRESET_NAME}"
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
  --build-arg BASE_ROCM_IMAGE=${PATCHED_ROCM_IMAGE}:${LLAMA_ROCM_VERSION}-complete \
  --build-arg LLAMACPP_REPO=$LLAMA_REPO \
  --build-arg LLAMACPP_BRANCH=$LLAMA_BRANCH \
  --build-arg LLAMACPP_COMMIT=$LLAMA_COMMIT \
  --build-arg LLAMACPP_CODE_PATH=$LLAMA_CODE_PATH \
  --progress=plain --target final -f llamacpp.Dockerfile ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
