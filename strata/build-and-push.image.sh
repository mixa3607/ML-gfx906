#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../env.sh "strata" "rocm" >&2
source ../.build/build-common.sh

if [ "$STRATA_PRESET_NAME" == "" ]; then
  STRATA_PRESET_NAME="${STRATA_BRANCH}-rocm-${STRATA_ROCM_VERSION}"
fi

STRATA_BASE_IMAGE="${ROCM_IMAGE}:${STRATA_ROCM_VERSION}-complete"
if [ "$STRATA_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "${STRATA_IMAGE}:${STRATA_PRESET_NAME}-${REPO_GIT_REF}"
    "${STRATA_IMAGE}:${STRATA_PRESET_NAME}"
  )
else
  IMAGE_TAGS=(
    "${STRATA_IMAGE}:${STRATA_PRESET_NAME}-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${STRATA_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$STRATA_BASE_IMAGE"

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/strata"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="Strata gfx906"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${STRATA_BASE_IMAGE}"

  echo "Start building Strata image..."
  echo "STRATA_REPO:    ${STRATA_REPO}"
  echo "STRATA_BRANCH:  ${STRATA_BRANCH}"
  echo "STRATA_COMMIT:  ${STRATA_COMMIT}"
  echo "STRATA_PATCH:   ${STRATA_PATCH}"
  echo "ROCM_ARCH:      ${ROCM_ARCH}"
  echo "ROCM_VERSION:   ${STRATA_ROCM_VERSION}"
  echo "IS_RELEASE:     ${STRATA_IS_RELEASE}"

  local -a DOCKER_EXTRA_ARGS=()
  local i key
  for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
    echo "TAG:          ${IMAGE_TAGS[$i]}"
    DOCKER_EXTRA_ARGS+=("--tag" "${IMAGE_TAGS[$i]}")
  done
  for key in "${!IMAGE_ANNOTATIONS[@]}"; do
    echo "ANNOTATION:   ${key}: ${IMAGE_ANNOTATIONS[$key]}"
    DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
  done

  DOCKER_EXTRA_ARGS+=(
    --build-arg ROCM_IMAGE="${STRATA_BASE_IMAGE}"
    --build-arg STRATA_REPO="${STRATA_REPO}"
    --build-arg STRATA_BRANCH="${STRATA_BRANCH}"
    --build-arg STRATA_COMMIT="${STRATA_COMMIT}"
    --build-arg STRATA_PATCH="${STRATA_PATCH}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$STRATA_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  echo "Build Strata"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
