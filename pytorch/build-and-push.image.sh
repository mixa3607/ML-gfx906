#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${TORCH_ROCM_VERSION:="7.14"}"
: "${TORCH_VERSION:="v2.13.0"}"
: "${TORCH_IMAGE:="docker.io/mixa3607/pytorch-gfx906"}"
: "${TORCH_PUSH:="1"}"
: "${TORCH_IS_RELEASE:="0"}"
: "${TORCH_PACKAGES_SOURCE:="fetch"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"

TORCH_VERSION_SUFFIX="${ROCM_ARCH}.${REPO_GIT_REF}"
TORCH_BASE_IMAGE="${ROCM_IMAGE}:${TORCH_ROCM_VERSION}-complete"
TORCH_PACKAGES_DIR="$PWD/output/rocm${TORCH_ROCM_VERSION}/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}"
TORCH_PACKAGES_URL="https://s3.arkprojects.space/py-gfx906/rocm${TORCH_ROCM_VERSION}/torch-${TORCH_VERSION}+${TORCH_VERSION_SUFFIX}"
if [ "$TORCH_IS_RELEASE" == "1" ]; then
  IMAGE_TAGS=(
    "$TORCH_IMAGE:${TORCH_VERSION}-rocm-${TORCH_ROCM_VERSION}-${REPO_GIT_REF}"
    "$TORCH_IMAGE:${TORCH_VERSION}-rocm-${TORCH_ROCM_VERSION}"
  )
else
  IMAGE_TAGS=(
    "$TORCH_IMAGE:${TORCH_VERSION}-rocm-${TORCH_ROCM_VERSION}-${REPO_GIT_REF}-pre"
  )
fi

function check {
  build_check_image "${IMAGE_TAGS[0]}" "${TORCH_FORCE_BUILD:-0}"
}

function build {
  build_require_images "$TORCH_BASE_IMAGE"

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/pytorch"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="PyTorch gfx906"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${TORCH_BASE_IMAGE}"

  print INFO "Start building PyTorch image..."
  print INFO "TORCH_VERSION:        ${TORCH_VERSION}"
  print INFO "TORCH VERSION SUFFIX: ${TORCH_VERSION_SUFFIX}"
  print INFO "TORCH PACKAGES SRC:   ${TORCH_PACKAGES_SOURCE}"
  print INFO "TORCH PACKAGES DIR:   ${TORCH_PACKAGES_DIR}"
  print INFO "TORCH PACKAGES URL:   ${TORCH_PACKAGES_URL}"
  print INFO "ROCM IMAGE:           ${TORCH_BASE_IMAGE}"
  print INFO "ROCM ARCH:            ${ROCM_ARCH}"
  print INFO "ROCM VERSION:         ${TORCH_ROCM_VERSION}"
  print INFO "PUSH:                 ${TORCH_PUSH}"
  print INFO "IS_RELEASE:           ${TORCH_IS_RELEASE}"

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
    --build-arg "BASE_ROCM_IMAGE=${TORCH_BASE_IMAGE}"
    --build-arg "ROCM_ARCH=${ROCM_ARCH}"
    --build-arg "VERSION_SUFFIX=${TORCH_VERSION_SUFFIX}"
    --build-arg "PYTORCH_BRANCH=${TORCH_VERSION}"
    --build-arg "PYTORCH_MAX_JOBS=${TORCH_MAX_JOBS}"
    --build-arg "PYTORCH_VISION_BRANCH=${TORCH_VISION_VERSION}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$TORCH_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  if [ "$TORCH_PACKAGES_SOURCE" == "fetch" ]; then
    DOCKER_EXTRA_ARGS+=(
      --build-arg "PACKAGE_SOURCE=fetch"
      --build-arg "PACKAGES_BASE_URL=$TORCH_PACKAGES_URL"
      --build-context "packages=$(mktemp -d)"
    )
  elif [ "$TORCH_PACKAGES_SOURCE" == "context" ]; then
    if ! [ -d "$TORCH_PACKAGES_DIR" ]; then
      print ERR "$TORCH_PACKAGES_DIR not exist. Try \"fetch\" source type"
      return 1
    fi
    DOCKER_EXTRA_ARGS+=(
      --build-arg "PACKAGE_SOURCE=context"
      --build-context "packages=$TORCH_PACKAGES_DIR"
    )
  else
    print ERR "TORCH_PACKAGES_SOURCE=$TORCH_PACKAGES_SOURCE not supported"
    return 1
  fi

  mkdir -p ./logs
  print INFO "Install torch whl packages to image"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
