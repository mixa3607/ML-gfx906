#!/bin/bash

export LLAMA_ROCM_VERSION="7.14"
export LLAMA_REPO="https://github.com/ggml-org/llama.cpp.git"
export LLAMA_BRANCH='b10288'
export LLAMA_PRESET_NAME="${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}"
export LLAMA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
