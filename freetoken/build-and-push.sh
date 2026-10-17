#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

FREETOKEN_SOURCE="${FREETOKEN_SOURCE:-$HOME/REPOS/FlashML-org/FreeToken}"
TRITON_SOURCE="${TRITON_SOURCE:-$HOME/REPOS/Dao-AILab/triton-gfx906}"
IMAGE="${IMAGE:-registry.arkprojects.space/apps/freetoken-gfx906:11c1adb-rocm7.14-torch2.13}"

docker buildx build --progress=plain \
  --build-context "freetoken-source=$FREETOKEN_SOURCE" \
  --build-context "triton-source=$TRITON_SOURCE" \
  --file build-image.Dockerfile --tag "$IMAGE" --push .
