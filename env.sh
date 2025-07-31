if [ "$ROCM_VERSION" == "" ]; then
  ROCM_VERSION=6.4.2
fi

if [ "$ROCM_ARCH" == "" ]; then
  ROCM_ARCH=gfx906
fi

if [ "$BASE_ROCM_REGISTRY" == "" ]; then
  BASE_ROCM_REGISTRY=registry.arkprojects.space/dockerio-proxy/rocm
fi
if [ "$PATCHED_ROCM_REGISTRY" == "" ]; then
  PATCHED_ROCM_REGISTRY=registry.arkprojects.space/apps/rocm
fi
if [ "$PATCHED_LLAMA_REGISTRY" == "" ]; then
  PATCHED_LLAMA_REGISTRY=registry.arkprojects.space/apps
fi


if [ "$REPO_GIT_REF" == "" ]; then
  REPO_GIT_REF="$(git tag --points-at HEAD)"
fi
if [ "$REPO_GIT_REF" == "" ]; then
  REPO_GIT_REF="$(git rev-parse --short HEAD)"
fi

if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(cd llama.cpp; git tag --points-at HEAD)"
fi
if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(cd llama.cpp; git rev-parse --short HEAD)"
fi
