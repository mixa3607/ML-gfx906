#!/bin/bash

# Qwen3.8-Flash-Next (qwen4exp) support is currently provided by Unsloth's
# llama.cpp branch, upstreamed as ggml-org/llama.cpp PR #27742.
export LLAMA_ROCM_VERSION="7.14"
export LLAMA_REPO="https://github.com/unslothai/llama.cpp.git"
export LLAMA_BRANCH='qwen4exp/qwen3.8-flash-next'
export LLAMA_COMMIT='035e227'
export LLAMA_PRESET_NAME="${LLAMA_COMMIT}-rocm-${LLAMA_ROCM_VERSION}-unsloth"
export LLAMA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
