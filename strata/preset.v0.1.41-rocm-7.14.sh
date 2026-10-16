#!/bin/bash

export STRATA_ROCM_VERSION="7.14"
export STRATA_REPO="https://github.com/Niko1221/Strata.git"
export STRATA_BRANCH="v0.1.41"
export STRATA_PRESET_NAME="${STRATA_BRANCH}-rocm-${STRATA_ROCM_VERSION}"
export STRATA_PATCH="gfx906-setup.patch"
