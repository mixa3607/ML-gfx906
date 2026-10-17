#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_VERSION:="7.14"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_BUILD:="${ROCM_VERSION}.0-${ROCM_ARCH}+${REPO_GIT_REF}"}"
: "${ROCM_BASE_IMAGE:="docker.io/library/ubuntu:24.04"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${ROCM_PUSH:="1"}"
: "${ROCM_IS_RELEASE:="0"}"

if [ "$ROCM_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "$ROCM_IMAGE:${ROCM_VERSION}-complete-${REPO_GIT_REF}"
    "$ROCM_IMAGE:${ROCM_VERSION}-complete"
  )
else
  IMAGE_TAGS=(
    "$ROCM_IMAGE:${ROCM_VERSION}-complete-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${ROCM_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$ROCM_BASE_IMAGE"

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/rocm"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="ROCm gfx906"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${ROCM_BASE_IMAGE}"

  print INFO "Start building ROCm image..."
  print INFO "ROCM_VERSION: ${ROCM_VERSION}"
  print INFO "ROCM_BUILD:   ${ROCM_BUILD}"
  print INFO "IS_RELEASE:   ${ROCM_IS_RELEASE}"

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
    --build-arg "ROCM_BASE_IMAGE=${ROCM_BASE_IMAGE}"
    --build-arg "ROCM_BUILD=${ROCM_BUILD}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$ROCM_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  print INFO "Install ROCm packages to image"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
