#!/usr/bin/env bash

if [ "$LLAMA_IMAGE" == "" ]; then
  LLAMA_IMAGE=docker.io/mixa3607/llama.cpp-multiruntime
fi
if [ "$LLAMA_ROCM_IMAGE" == "" ]; then
  LLAMA_ROCM_IMAGE=docker.io/mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14
fi
if [ "$LLAMA_CUDA_IMAGE" == "" ]; then
  LLAMA_CUDA_IMAGE=docker.io/mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn
fi
if [ "$LLAMA_IS_RELEASE" == "" ]; then
  LLAMA_IS_RELEASE=0
fi
if [ "$LLAMA_PUSH" == "" ]; then
  LLAMA_PUSH=1
fi
