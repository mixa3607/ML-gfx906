#!/bin/bash

export VLLM_ROCM_VERSION="7.2.1"
export VLLM_PYTORCH_VERSION="v2.11.0"

export VLLM_REPO="https://github.com/ai-infos/vllm-gfx906-mobydick.git"
export VLLM_BRANCH="main"
export VLLM_COMMIT="eb450bd"

export VLLM_TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"
export VLLM_TRITON_BRANCH="v3.6.0+gfx906"

export VLLM_FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"
export VLLM_FA_BRANCH="gfx906/v2.8.3.x"
export VLLM_FA_COMMIT="0ac8e77"

export VLLM_PRESET_NAME="0.20.1-rocm-$VLLM_ROCM_VERSION-aiinfos"
export VLLM_EXTRA_REQUIREMENTS="ai-infos_vllm-gfx906-mobydick/$VLLM_COMMIT.txt"
