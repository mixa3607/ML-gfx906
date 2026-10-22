#!/bin/bash

export LLAMA_ROCM_VERSION="10.1"
export LLAMA_REPO="https://github.com/unslothai/llama.cpp.git"
export LLAMA_BRANCH='b11734-mix-c208e5f'
export LLAMA_PRESET_NAME="${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}-unsloth"
export LLAMA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
