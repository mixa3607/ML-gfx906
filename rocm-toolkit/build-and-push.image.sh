#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_TOOLKIT_IMAGE:="docker.io/mixa3607/rocm-toolkit-gfx906"}"
: "${ROCM_TOOLKIT_PUSH:="1"}"
: "${ROCM_TOOLKIT_IS_RELEASE:="0"}"
: "${ROCM_VERSION:="7.14"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${BASE_ROCM_IMAGE:="${ROCM_IMAGE}:${ROCM_VERSION}-complete"}"

if [ "$ROCM_TOOLKIT_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "$ROCM_TOOLKIT_IMAGE:${ROCM_VERSION}-${REPO_GIT_REF}"
    "$ROCM_TOOLKIT_IMAGE:${ROCM_VERSION}"
  )
else
  IMAGE_TAGS=(
    "$ROCM_TOOLKIT_IMAGE:${ROCM_VERSION}-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${ROCM_TOOLKIT_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$BASE_ROCM_IMAGE"

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/rocm-toolkit"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="ROCm gfx906 toolkit"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${BASE_ROCM_IMAGE}"

  print INFO "Start building ROCm toolkit image..."
  print INFO "ROCm base image: ${BASE_ROCM_IMAGE}"
  print INFO "ROCm version:    ${ROCM_VERSION}"
  print INFO "Is release:      ${ROCM_TOOLKIT_IS_RELEASE}"
  print INFO "Push:            ${ROCM_TOOLKIT_PUSH}"

  local -a DOCKER_EXTRA_ARGS=()
  local image_tag key
  for image_tag in "${IMAGE_TAGS[@]}"; do
    print INFO "Tag:             ${image_tag}"
    DOCKER_EXTRA_ARGS+=("--tag" "${image_tag}")
  done
  for key in "${!IMAGE_ANNOTATIONS[@]}"; do
    DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
  done

  DOCKER_EXTRA_ARGS+=(
    --build-arg "BASE_ROCM_IMAGE=${BASE_ROCM_IMAGE}"
    --build-arg "ROCM_VERSION=${ROCM_VERSION}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$ROCM_TOOLKIT_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" . 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
