#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$PATCHED_LLAMA_REGISTRY" == "" ]; then
  PATCHED_LLAMA_REGISTRY=ghcr.io/mixa3607/ml-gfx906/llama
fi

if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(cd submodules/llama.cpp; git tag --points-at HEAD)"
fi
if [ "$LLAMA_GIT_REF" == "" ]; then
  LLAMA_GIT_REF="$(cd submodules/llama.cpp; git rev-parse --short HEAD)"
fi

popd
