#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source ./env.sh

args=(
  --platform linux/amd64
  --target final
  --tag "${LLAMA_IMAGE}:${LLAMA_TAG}"
  --build-arg "ROCM_IMAGE=${LLAMA_ROCM_IMAGE}"
  --build-arg "CUDA_IMAGE=${LLAMA_CUDA_IMAGE}"
  --progress plain
  --pull
)
if [[ "$LLAMA_PUSH" == 1 ]]; then
  args+=(--push)
else
  args+=(--load)
fi

mkdir -p logs
docker buildx build "${args[@]}" "$@" - < ./build-image.Dockerfile 2>&1 | tee "logs/build_$(date +%Y%m%d%H%M%S).log"
