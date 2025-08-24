#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$PATCHED_LLAMA_REGISTRY" == "" ]; then
  PATCHED_LLAMA_REGISTRY=ghcr.io/mixa3607/ml-gfx906/llama
fi

if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(git_get_current_tag submodules/llama.cpp)"
fi
if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(git_get_current_sha submodules/llama.cpp)"
fi

popd
