#!/bin/bash

export VLLM_VERSION="0.28.0rc2"
export VLLM_ROCM_VERSION="7.14"
export VLLM_PYTORCH_VERSION="v2.13.0"

# KIntegrated vLLM gfx906/v0.28.0rc2: upstream v0.28.0rc2 merged onto the
# gfx906 fork line (gfx906/main is fully contained in this branch).
# VLLM_VERSION is applied as a local git tag so setuptools-scm reports it
# (see AGENTS.md). The vllm short commit is kept in the image tag for build
# metadata while this is a prerelease.
export VLLM_REPO="https://github.com/KIntegrated/vllm-gfx906-mobydick.git"
export VLLM_BRANCH="gfx906/v0.28.0rc2"
export VLLM_COMMIT="19e23ffedd"

# triton / flash-attention: validated gfx906 forks (unchanged from 0.26.0)
export VLLM_TRITON_REPO="https://github.com/ai-infos/triton-gfx906.git"
export VLLM_TRITON_BRANCH="v3.6.0+gfx906"

export VLLM_FA_REPO="https://github.com/ai-infos/flash-attention-gfx906.git"
export VLLM_FA_BRANCH="gfx906/v2.8.3.x"
export VLLM_FA_COMMIT="0ac8e77"

export VLLM_PRESET_NAME="${VLLM_VERSION}-${VLLM_COMMIT}-rocm-${VLLM_ROCM_VERSION}-kintegrated"
export VLLM_EXTRA_REQUIREMENTS="KIntegrated_vllm-gfx906-mobydick/${VLLM_COMMIT}.txt"
