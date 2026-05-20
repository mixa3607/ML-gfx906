#!/bin/bash

# https://github.com/ggml-org/llama.cpp/pull/23398
export LLAMA_ROCM_VERSION='7.2.3'
export LLAMA_BRANCH='gemma4-mtp'
export LLAMA_COMMIT='a03120c'
export LLAMA_CODE_PATH=""
export LLAMA_PRESET_NAME="${LLAMA_COMMIT}-rocm-${LLAMA_ROCM_VERSION}-am17an"
export LLAMA_REPO="https://github.com/am17an/llama.cpp.git"
