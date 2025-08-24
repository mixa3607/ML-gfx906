#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-vulkan"
  "$PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-vulkan-patch-${REPO_GIT_REF}"
  "$PATCHED_LLAMA_REGISTRY/llamacpp:full-latest-vulkan"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

docker buildx build ${IMAGE_TAGS[@]/#/-t } \
  --build-arg UBUNTU_VERSION="24.04" \
  --progress=plain --target full -f ./submodules/llama.cpp/.devops/vulkan.Dockerfile --push ./submodules/llama.cpp
