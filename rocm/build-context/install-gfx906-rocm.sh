#!/bin/bash
set -eo pipefail

echo "Searching rocm $ROCM_BUILD packages"
MAJOR_MINOR=$(echo "$ROCM_BUILD" | grep -oE '^[0-9]+\.[0-9]+')
GPU_TARGET=$(echo "$ROCM_BUILD" | grep -oE 'gfx[0-9]+')
ROCM_PACKAGES=(
  amdrocm${MAJOR_MINOR}=${ROCM_BUILD}
  amdrocm-core-sdk${MAJOR_MINOR}=${ROCM_BUILD} 
  amdrocm${MAJOR_MINOR}-${GPU_TARGET}=${ROCM_BUILD} 
  amdrocm-core-sdk${MAJOR_MINOR}-${GPU_TARGET}=${ROCM_BUILD} 
)
echo "Rocm packages to install: ${ROCM_PACKAGES[@]}" 
apt-get install --no-install-recommends -y "${ROCM_PACKAGES[@]}"

echo "Add ROCm to libs"
tee /etc/ld.so.conf.d/rocm.conf <<EOF
# ROCm gfx906
$ROCM_PATH/lib
EOF
ldconfig
