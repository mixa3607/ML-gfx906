#!/bin/bash

export VLLM_ROCM_VERSION="6.3.3"
export VLLM_PYTORCH_VERSION="v2.8.0"
export VLLM_REPO="https://github.com/tomylin890/vllm-gfx906.git"
export VLLM_BRANCH="gfx906/v0.11.0"
export VLLM_TRITON_BRANCH="v3.4.0+gfx906"
export VLLM_PRESET_NAME="0.11.0-rocm-$VLLM_ROCM_VERSION-tomylin890"
export VLLM_IMAGE="registry.arkprojects.space/apps/vllm-gfx906"