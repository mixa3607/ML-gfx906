#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$PATCHED_VLLM_IMAGE:${VLLM_GIT_REF}-triton-${TRITON_GIT_REF}-rocm-${VLLM_ROCM_VERSION}"
  "$PATCHED_VLLM_IMAGE:${VLLM_GIT_REF}-triton-${TRITON_GIT_REF}-rocm-${VLLM_ROCM_VERSION}-patch-${REPO_GIT_REF}"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  IMAGE_TAGS[$i]="-t ${IMAGE_TAGS[$i]}"
done

docker buildx build ${IMAGE_TAGS[@]} --push \
  --build-arg BASE_ROCM_IMAGE=$PATCHED_ROCM_IMAGE:${VLLM_ROCM_VERSION}-complete \
  --progress=plain --target final -f ./vllm.Dockerfile ./submodules
