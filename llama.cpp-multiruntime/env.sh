#!/usr/bin/env bash

: "${LLAMA_IMAGE:=registry.arkprojects.space/apps/llama.cpp-multiruntime}"
: "${LLAMA_TAG:=v0.5.0-rocm-7.14-cuda-13.3.0-rocm-base-smoke}"
: "${LLAMA_ROCM_IMAGE:=docker.io/mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14@sha256:32ab18dd9c957bb99c1aded8fb93dc40b3fd51b39fc6d142714f51fbc81cfe8c}"
: "${LLAMA_CUDA_IMAGE:=docker.io/mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn@sha256:e4d9f6020862b1160406c51403a4629ba1a341e1c4cbfdfc7d0e7a5cc1e3b0cd}"
: "${LLAMA_PUSH:=1}"
