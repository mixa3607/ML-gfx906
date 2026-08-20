#!/bin/bash

export VLLM_VERSION="0.26.0"
export VLLM_ROCM_VERSION="6.3.3"
export VLLM_PYTORCH_VERSION="v2.11.0"

# KIntegrated vLLM 0.26.0 port (gfx906/mobydick fork)
export VLLM_REPO="https://github.com/KIntegrated/vllm-gfx906-mobydick.git"
export VLLM_BRANCH="gfx906/v0.26.0rc0.x"
export VLLM_COMMIT="75765d1116"

# triton / flash-attention: validated forks, unchanged from 0.20.1
export VLLM_TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"
export VLLM_TRITON_BRANCH="v3.6.0+gfx906"

export VLLM_FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"
export VLLM_FA_BRANCH="gfx906/v2.8.3.x"
export VLLM_FA_COMMIT="0ac8e77"

export VLLM_PRESET_NAME="${VLLM_VERSION}-rocm-$VLLM_ROCM_VERSION-kintegrated"
export VLLM_EXTRA_REQUIREMENTS="KIntegrated_vllm-gfx906-mobydick/$VLLM_COMMIT.txt"
