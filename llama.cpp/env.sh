#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$PATCHED_LLAMA_IMAGE" == "" ]; then
  PATCHED_LLAMA_IMAGE=docker.io/mixa3607/llama.cpp-gfx906:full-rocm-7.0.0
fi

# rocm ver
if [ "$LLAMA_ROCM_VERSION" == "" ]; then
  LLAMA_ROCM_VERSION=7.0.0
fi

if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(git_get_current_tag submodules/llama.cpp)"
fi
if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(git_get_current_sha submodules/llama.cpp)"
fi

popd
