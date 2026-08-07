#!/bin/bash

export LLAMA_ROCM_VERSION='7.14'
export LLAMA_BRANCH='b10288'
export LLAMA_PRESET_NAME='b10288-rocm-7.14'
export LLAMA_CMAKE_HIP_FLAGS='-mllvm -amdgpu-sched-strategy=max-ilp'
export LLAMA_PATCH="empty.patch"
