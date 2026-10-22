#!/usr/bin/env bash

export LLAMA_ROCM_IMAGE="registry.arkprojects.space/apps/llama.cpp-gfx906:b11734-mix-c208e5f-rocm-10.1-unsloth-fix-mix-source-pre@sha256:00eb91d76e05a0cc017b27685eac77c0b76362240d9b9779b7220507986f4752"
export LLAMA_CUDA_IMAGE="registry.arkprojects.space/apps/llama.cpp-sm120:b11734-mix-c208e5f-cuda-13.4.2-cudnn-unsloth-fix-mix-source-pre@sha256:a016ae360d3bed5e4d632cce62ac86fc167297f2f56716273feb0769563fd545"
export LLAMA_PRESET_NAME="b11734-mix-c208e5f-rocm-10.1-cuda-13.4.2-unsloth"
