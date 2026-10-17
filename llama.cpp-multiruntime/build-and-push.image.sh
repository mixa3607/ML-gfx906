#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${LLAMA_IMAGE:="docker.io/mixa3607/llama.cpp-gfx906"}"
: "${LLAMA_ROCM_IMAGE:="docker.io/mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14"}"
: "${LLAMA_CUDA_IMAGE:="docker.io/mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn"}"
: "${LLAMA_IS_RELEASE:="0"}"
: "${LLAMA_PUSH:="1"}"

if [ "$LLAMA_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "${LLAMA_IMAGE}:${LLAMA_PRESET_NAME}-${REPO_GIT_REF}"
    "${LLAMA_IMAGE}:${LLAMA_PRESET_NAME}"
  )
else
  IMAGE_TAGS=(
    "${LLAMA_IMAGE}:${LLAMA_PRESET_NAME}-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${LLAMA_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$LLAMA_ROCM_IMAGE" "$LLAMA_CUDA_IMAGE"

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/llama.cpp-multiruntime"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="Llama.cpp multiruntime"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${LLAMA_ROCM_IMAGE}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.cuda.base.name"]="${LLAMA_CUDA_IMAGE}"

  print INFO "Start building llama.cpp multiruntime image..."
  print INFO "ROCM_IMAGE:     ${LLAMA_ROCM_IMAGE}"
  print INFO "CUDA_IMAGE:     ${LLAMA_CUDA_IMAGE}"
  print INFO "IS_RELEASE:     ${LLAMA_IS_RELEASE}"

  local -a DOCKER_EXTRA_ARGS=()
  local i key
  for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
    print INFO "TAG:          ${IMAGE_TAGS[$i]}"
    DOCKER_EXTRA_ARGS+=("--tag" "${IMAGE_TAGS[$i]}")
  done
  for key in "${!IMAGE_ANNOTATIONS[@]}"; do
    print INFO "ANNOTATION:   ${key}: ${IMAGE_ANNOTATIONS[$key]}"
    DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
  done

  DOCKER_EXTRA_ARGS+=(
    --platform linux/amd64
    --build-arg ROCM_IMAGE="${LLAMA_ROCM_IMAGE}"
    --build-arg CUDA_IMAGE="${LLAMA_CUDA_IMAGE}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$LLAMA_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  print INFO "Build llama.cpp multiruntime"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
