#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$PATCHED_LLAMA_IMAGE:full-${LLAMA_GIT_REF}-vulkan-patch-${REPO_GIT_REF}"
  "$PATCHED_LLAMA_IMAGE:full-${LLAMA_GIT_REF}-vulkan"
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
  --build-arg UBUNTU_VERSION="24.04" \
  --progress=plain --target full -f ./submodules/llama.cpp/.devops/vulkan.Dockerfile ./submodules/llama.cpp 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
