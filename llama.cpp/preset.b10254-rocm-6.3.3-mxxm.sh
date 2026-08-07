#!/bin/bash

export LLAMA_ROCM_VERSION="6.3.3"
export LLAMA_REPO="https://github.com/mxxm-t/mx-llama.cpp.git"
export LLAMA_BRANCH='b10254'
export LLAMA_PRESET_NAME="${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}-mxxm"
export LLAMA_CMAKE_HIP_FLAGS=""
export LLAMA_PATCH="empty.patch"
