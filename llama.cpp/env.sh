#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$LLAMA_IMAGE" == "" ]; then
  LLAMA_IMAGE=docker.io/mixa3607/llama.cpp-gfx906
fi

# rocm ver
if [ "$LLAMA_ROCM_VERSION" == "" ]; then
  LLAMA_ROCM_VERSION=7.14
fi

if [ "$LLAMA_REPO" == "" ]; then
  LLAMA_REPO="https://github.com/ggml-org/llama.cpp.git"
fi
if [ "$LLAMA_BRANCH" == "" ]; then
  LLAMA_BRANCH="master"
fi
if [ "$LLAMA_COMMIT" == "" ]; then
  LLAMA_COMMIT=""
fi

# push image
if [ "$LLAMA_PUSH" == "" ]; then
  LLAMA_PUSH="1"
fi

popd
