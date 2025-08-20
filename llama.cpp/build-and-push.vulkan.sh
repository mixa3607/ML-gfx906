#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

docker buildx build --builder=remote \
  --build-arg UBUNTU_VERSION="24.04" \
  -t $PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-vulkan-patch-${REPO_GIT_REF} \
  -t $PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-vulkan \
  --progress=plain --target full -f ./submodules/llama.cpp/.devops/vulkan.Dockerfile --push ./submodules/llama.cpp
