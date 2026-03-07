#!/bin/bash

export VLLM_ROCM_VERSION="6.3.3"
export VLLM_PYTORCH_VERSION="v2.8.0"
export VLLM_PRESET_NAME="0.11.2-rocm-$VLLM_ROCM_VERSION-nlzy"

export VLLM_REPO="https://github.com/nlzy/vllm-gfx906.git"
export VLLM_BRANCH="v0.11.2+gfx906"
export VLLM_PATCH="nlzy_vllm-gfx906/$VLLM_BRANCH.patch"

export VLLM_TRITON_REPO="https://github.com/nlzy/triton-gfx906.git"
export VLLM_TRITON_BRANCH="v3.4.0+gfx906"
