#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

ROCM_VERSION=6.3.3
IMAGE_TAGS=(
  "$PATCHED_VLLM_REGISTRY/vllm:${VLLM_GIT_REF}-triton-${TRITON_GIT_REF}-rocm-${ROCM_VERSION}"
  "$PATCHED_VLLM_REGISTRY/vllm:${VLLM_GIT_REF}-triton-${TRITON_GIT_REF}-rocm-${ROCM_VERSION}-patch-${REPO_GIT_REF}"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  IMAGE_TAGS[$i]="--output type=image,name=${IMAGE_TAGS[$i]},push=true,push-by-digest=false,compression=zstd"
done

docker buildx build ${IMAGE_TAGS[@]} \
  --build-arg BASE_ROCM_IMAGE=$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-complete \
  --progress=plain --target final -f ./vllm.Dockerfile ./submodules
