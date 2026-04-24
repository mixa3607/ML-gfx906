#/bin/bash
set -e
set -o pipefail

cd $(dirname $0)
source ../env.sh "llama.cpp"

IMAGE_TAGS=(
  "${LLAMA_IMAGE}:${LLAMA_PRESET_NAME}"
  "${LLAMA_IMAGE}:${LLAMA_PRESET_NAME}-${REPO_GIT_REF}"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo -n "${IMAGE_TAGS[0]} already in registry. "
  if [ "$LLAMA_FORCE_BUILD" == "1" ]; then
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

mkdir -p ./logs || true
docker buildx build ${DOCKER_EXTRA_ARGS[@]} --push \
  --build-arg BASE_CUDA_IMAGE=${LLAMA_CUDA_IMAGE}:${LLAMA_CUDA_VERSION}-devel-ubuntu22.04 \
  --build-arg LLAMACPP_REPO=$LLAMA_REPO \
  --build-arg LLAMACPP_BRANCH=$LLAMA_BRANCH \
  --build-arg LLAMACPP_COMMIT=$LLAMA_COMMIT \
  --build-arg LLAMACPP_CODE_PATH=$LLAMA_CODE_PATH \
  --progress=plain --target final -f llamacpp.Dockerfile ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
