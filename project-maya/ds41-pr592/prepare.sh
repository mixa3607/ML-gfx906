#!/usr/bin/env bash
set -euo pipefail
test -f /existing/ds4/tensors.txt
test -f /existing/expert-profile.bin
test -f /existing/vision/vision.bin
test -f /existing/drafter/dspark.bin
# Reuse the existing pack and its absolute /data paths without changing it.
ln -s /existing/ds4 /data/ds4
ln -s /existing/vision /data/vision
ln -s /existing/drafter /data/drafter
cp /existing/expert-profile.bin /data/seed-profile.bin
sha256sum /data/seed-profile.bin /data/ds4/tensors.txt
cat /opt/maya/SOURCE_COMMIT
