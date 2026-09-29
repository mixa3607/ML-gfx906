#!/bin/bash

export LLAMA_ROCM_VERSION="10.0"
export LLAMA_REPO="https://github.com/mxxm-t/mx-llama.cpp.git"
export LLAMA_BRANCH='b10951'
export LLAMA_PRESET_NAME="${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}-mxxm"
export LLAMA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
