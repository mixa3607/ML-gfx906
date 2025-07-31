source env.sh
docker buildx build --builder=remote \
  --build-arg BASE_ROCM_DEV_CONTAINER=$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-${REPO_GIT_REF}-complete \
  --build-arg ROCM_DOCKER_ARCH=$ROCM_ARCH \
  --build-arg ROCM_VERSION=$ROCM_VERSION \
  --build-arg AMDGPU_VERSION=$ROCM_VERSION \
  -t $PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-rocm-${ROCM_VERSION}-patch-${REPO_GIT_REF} \
  -t $PATCHED_LLAMA_REGISTRY/llamacpp:full-${LLAMA_GIT_REF}-rocm-${ROCM_VERSION} \
  --target full -f ./llama.cpp/.devops/rocm.Dockerfile --push ./llama.cpp
