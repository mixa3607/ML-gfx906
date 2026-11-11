#!/usr/bin/env bash
# DeepSeek-V4.1-Flash for gfx906. Upstream Strata does not build strata-dsv41
# on this architecture until https://github.com/Niko1221/Strata/pull/5739 is
# merged, so this preset clones that branch and pins the commit.
# llama.cpp is still the checkout setup.get_llama_cpp() downloads.

export STRATA_ROCM_VERSION="10.1"
export STRATA_REPO="https://github.com/shjszwh/mi50-Strata.git"
export STRATA_BRANCH="gfx906-dsv41"
export STRATA_COMMIT="9898718423ed1f319730fc65bac9a11a17c49988"
export STRATA_PATCH="empty.patch"
export STRATA_BUILD_DSV41="1"
export STRATA_PRESET_NAME="deepseek41-rocm-${STRATA_ROCM_VERSION}"
