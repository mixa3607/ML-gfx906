#!/bin/bash

export STRATA_ROCM_VERSION="10.1"
export STRATA_REPO="https://github.com/Niko1221/Strata.git"
export STRATA_BRANCH="v0.2.0-beta"
export STRATA_PRESET_NAME="${STRATA_BRANCH}-rocm-${STRATA_ROCM_VERSION}"
export STRATA_PATCH="gfx906-setup.patch"
export STRATA_CMAKE_HIP_FLAGS="-mllvm -amdgpu-sched-strategy=max-ilp"
