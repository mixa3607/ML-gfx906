#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

docker buildx build --builder=remote \
  --build-arg BASE_ROCM_DEV_CONTAINER=$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-complete \
  --build-arg ROCM_DOCKER_ARCH=$ROCM_ARCH \
  --build-arg ROCM_VERSION=$ROCM_VERSION \
  --build-arg AMDGPU_VERSION=$ROCM_VERSION \
  -t $PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-rocm-${ROCM_VERSION}-patch-${REPO_GIT_REF} \
  -t $PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-rocm-${ROCM_VERSION} \
  --progress=plain --target full -f ./submodules/llama.cpp/.devops/rocm.Dockerfile --push ./submodules/llama.cpp
