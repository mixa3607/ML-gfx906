#/bin/bash

pushd $(dirname ${BASH_SOURCE[0]})

if [ "$LLAMA_IMAGE" == "" ]; then
  LLAMA_IMAGE=docker.io/mixa3607/llama.cpp-sm120
fi

if [ "$LLAMA_CUDA_IMAGE" == "" ]; then
  LLAMA_CUDA_IMAGE="docker.io/nvidia/cuda"
fi
if [ "$LLAMA_CUDA_VERSION" == "" ]; then
  LLAMA_CUDA_VERSION="13.2.1-cudnn"
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

popd
