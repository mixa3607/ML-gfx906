#!/usr/bin/env bash

: "${LLAMA_IMAGE:=registry.arkprojects.space/apps/llama.cpp-multiruntime}"
: "${LLAMA_TAG:=v0.5.0-rocm-7.14-cuda-13.3.0-smoke}"
: "${LLAMA_ROCM_IMAGE:=docker.io/mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14@sha256:32ab18dd9c957bb99c1aded8fb93dc40b3fd51b39fc6d142714f51fbc81cfe8c}"
: "${LLAMA_CUDA_IMAGE:=docker.io/mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn@sha256:e4d9f6020862b1160406c51403a4629ba1a341e1c4cbfdfc7d0e7a5cc1e3b0cd}"
: "${LLAMA_REPO:=https://github.com/ggml-org/llama.cpp.git}"
: "${LLAMA_BRANCH:=v0.5.0}"
: "${LLAMA_COMMIT:=7fe450e19305b828c199d602c23a8337aaa1f03b}"
: "${LLAMA_ROCM_BUILD:=7.14.0-gfx906+20260802001858}"
: "${LLAMA_BUILD_JOBS:=8}"
: "${LLAMA_PUSH:=1}"
