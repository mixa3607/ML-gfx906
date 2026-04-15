#!/bin/bash

export LLAMA_ROCM_VERSION='7.2.1'
export LLAMA_BRANCH='main'
export LLAMA_COMMIT='a60244a'
export LLAMA_CODE_PATH="llama-cpp-gfx906-turbo"
export LLAMA_PRESET_NAME="${LLAMA_COMMIT}-rocm-${LLAMA_ROCM_VERSION}-artefact"
export LLAMA_REPO="https://github.com/arte-fact/llamacpp-gfx-906-turbo.git"
