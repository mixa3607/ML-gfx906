#!/bin/bash

export LLAMA_ROCM_VERSION='7.2.1'
export LLAMA_BRANCH='feature/turboquant-kv-cache'
export LLAMA_COMMIT='69d8e4b'
export LLAMA_PRESET_NAME="${LLAMA_COMMIT}-rocm-${LLAMA_ROCM_VERSION}-thetom"
export LLAMA_REPO="https://github.com/TheTom/llama-cpp-turboquant.git"
