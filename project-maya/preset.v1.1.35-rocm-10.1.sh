#!/usr/bin/env bash
export MAYA_ROCM_VERSION="10.1"
export MAYA_REPO="https://github.com/mw00/project-maya.git"
export MAYA_BRANCH="v1.1.35"
export MAYA_COMMIT="e16dec85abf8801a4cfc086ee4814071a3ff54a2"
export MAYA_PRESET_NAME="${MAYA_BRANCH}-rocm-${MAYA_ROCM_VERSION}"
export MAYA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
export MAYA_PATCH="v1.1.32.patch"
