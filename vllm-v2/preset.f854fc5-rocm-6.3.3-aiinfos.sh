#!/bin/bash

export VLLM_ROCM_VERSION="6.3.3"
export VLLM_PYTORCH_VERSION="v2.10.0"

export VLLM_REPO="https://github.com/ai-infos/vllm-gfx906-mobydick.git"
export VLLM_BRANCH="gfx906/v0.17.1rc0.x"
export VLLM_COMMIT="f854fc5"

export VLLM_TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"
export VLLM_TRITON_BRANCH="v3.5.1+gfx906"

export VLLM_FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"
export VLLM_FA_BRANCH="gfx906/v2.8.3.x"

export VLLM_PRESET_NAME="$VLLM_COMMIT-rocm-$VLLM_ROCM_VERSION-aiinfos"
