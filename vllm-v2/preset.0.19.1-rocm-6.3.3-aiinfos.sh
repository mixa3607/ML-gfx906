#!/bin/bash

export VLLM_ROCM_VERSION="6.3.3"
export VLLM_PYTORCH_VERSION="v2.11.0"

export VLLM_REPO="https://github.com/ai-infos/vllm-gfx906-mobydick.git"
export VLLM_BRANCH="gfx906/v0.19.1rc0.x"
export VLLM_COMMIT="2abb7c4b"
export VLLM_PATCH="ai-infos_vllm-gfx906-mobydick/$VLLM_COMMIT.patch"

export VLLM_TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"
export VLLM_TRITON_BRANCH="v3.6.0+gfx906"

export VLLM_FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"
export VLLM_FA_BRANCH="gfx906/v2.8.3.x"
export VLLM_FA_COMMIT="0ac8e77"

export VLLM_PRESET_NAME="0.19.1-rocm-$VLLM_ROCM_VERSION-aiinfos"
export VLLM_EXTRA_REQUIREMENTS="ai-infos_vllm-gfx906-mobydick/$VLLM_COMMIT.txt"
