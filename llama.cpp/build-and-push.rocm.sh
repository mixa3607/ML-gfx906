#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh "llama.cpp" "rocm" 

IMAGE_TAGS=(
  "$LLAMA_IMAGE:full-${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}-${REPO_GIT_REF}"
  "$LLAMA_IMAGE:full-${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}"
  "$LLAMA_IMAGE:full-rocm-${LLAMA_ROCM_VERSION}"
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
  --progress=plain --target final -f llamacpp.Dockerfile ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
