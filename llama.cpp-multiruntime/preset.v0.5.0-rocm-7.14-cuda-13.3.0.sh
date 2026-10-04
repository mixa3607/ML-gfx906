#!/usr/bin/env bash

export LLAMA_ROCM_IMAGE="registry.arkprojects.space/apps/llama.cpp-gfx906:v0.5.0-rocm-7.14-fac1c70-pre"
export LLAMA_CUDA_IMAGE="docker.io/mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.4.2-cudnn"
export LLAMA_PRESET_NAME="v0.5.0-rocm-7.14-cuda-13.4.2"
