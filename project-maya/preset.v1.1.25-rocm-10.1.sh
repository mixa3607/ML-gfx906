#!/usr/bin/env bash
export MAYA_ROCM_VERSION="10.1"
export MAYA_REPO="https://github.com/mw00/project-maya.git"
export MAYA_BRANCH="v1.1.25"
export MAYA_PRESET_NAME="${MAYA_BRANCH}-rocm-${MAYA_ROCM_VERSION}"
export MAYA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
export MAYA_PATCH="v1.1.25"
