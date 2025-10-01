#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

ROCM_VERSION=7.0.0
IMAGE_TAGS=(
  "$PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-rocm-${LLAMA_ROCM_VERSION}"
  "$PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-rocm-${LLAMA_ROCM_VERSION}-patch-${REPO_GIT_REF}"
  "$PATCHED_LLAMA_REGISTRY/llamacpp:full-latest-rocm"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

docker buildx build ${IMAGE_TAGS[@]/#/-t } \
  --build-arg BASE_ROCM_DEV_CONTAINER=$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${LLAMA_ROCM_VERSION}-complete \
  --build-arg ROCM_DOCKER_ARCH=$ROCM_ARCH \
  --build-arg ROCM_VERSION=$LLAMA_ROCM_VERSION \
  --build-arg AMDGPU_VERSION=$LLAMA_ROCM_VERSION \
  --progress=plain --target full -f ./submodules/llama.cpp/.devops/rocm.Dockerfile --push ./submodules/llama.cpp
