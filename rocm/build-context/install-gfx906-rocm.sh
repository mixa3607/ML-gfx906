#!/bin/bash
set -ex

echo "Searching rocm $ROCM_BUILD packages"
ROCM_PACKAGES="$(
  apt list | 
  sed -nE 's|^(.+)/(.+) (.+) (.+)$|{ "name": "\1", "version": "\3" }|1p' | 
  jq -r \
    --arg prefix amdrocm \
    --arg build "$ROCM_BUILD" \
  '
    select(.name | startswith($prefix)) | 
    select(.version == $build) | 
    .name + "=" + .version
  ' 
)"

ROCM_PACKAGES_COUNT="$(( $(echo "$ROCM_PACKAGES" | wc -l) -1 ))"
if [ "$ROCM_PACKAGES_COUNT" -eq 0 ]; then
  echo "No ROCm packages found. Exit 1"
  exit 1
fi

echo "Rocm packages to install ($ROCM_PACKAGES_COUNT): \n$ROCM_PACKAGES" 
apt-get install -y $ROCM_PACKAGES

echo "Add ROCm to libs"
tee /etc/ld.so.conf.d/rocm.conf <<EOF
# ROCm gfx906
$ROCM_PATH/lib
EOF
ldconfig
