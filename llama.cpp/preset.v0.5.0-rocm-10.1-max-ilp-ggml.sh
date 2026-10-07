#!/bin/bash

source "$(dirname "${BASH_SOURCE[0]}")/preset.v0.5.0-rocm-10.0-ggml.sh"
export LLAMA_ROCM_VERSION="10.1"
export LLAMA_PRESET_NAME="${LLAMA_BRANCH}-rocm-${LLAMA_ROCM_VERSION}-max-ilp"
