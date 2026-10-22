#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../.build/git-common.sh
source ../.build/logger.sh
source ../.build/build-common.sh

: "${REPO_GIT_REF:="$(git_get_current_ref)"}"
: "${ROCM_ARCH:="gfx906"}"
: "${ROCM_IMAGE:="docker.io/mixa3607/rocm-gfx906"}"
: "${LLAMA_IMAGE:="docker.io/mixa3607/llama.cpp-gfx906"}"
: "${LLAMA_ROCM_VERSION:="7.14"}"
: "${LLAMA_REPO:="https://github.com/ggml-org/llama.cpp.git"}"
: "${LLAMA_BRANCH:="master"}"
: "${LLAMA_COMMIT:=""}"
: "${LLAMA_CMAKE_HIP_FLAGS:=""}"
: "${LLAMA_CCACHE_MAXSIZE:="2G"}"
: "${LLAMA_IS_RELEASE:="0"}"
: "${LLAMA_PATCH:="empty.patch"}"
: "${LLAMA_PUSH:="1"}"
: "${LLAMA_BASE_IMAGE:="${ROCM_IMAGE}:${LLAMA_ROCM_VERSION}-complete"}"

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
  build_require_images "$LLAMA_BASE_IMAGE"

  local source_url="" source_sha256="" source
  if [[ "${LLAMA_REPO%.git}" == "https://github.com/unslothai/llama.cpp" && "$LLAMA_BRANCH" == b*-mix-* ]]; then
    if [ -n "$LLAMA_COMMIT" ]; then
      print ERROR "LLAMA_COMMIT cannot override an Unsloth mix release archive."
      return 1
    fi
    source="$(python3 ./resolve-unsloth-source.py "$LLAMA_BRANCH")"
    read -r source_url source_sha256 <<< "$source"
  fi

  local -A IMAGE_ANNOTATIONS
  IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
  IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
  IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/llama.cpp"
  IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
  IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="Llama.cpp gfx906"
  IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${LLAMA_BASE_IMAGE}"

  print INFO "Start building llama.cpp image..."
  print INFO "LLAMA_REPO:       ${LLAMA_REPO}"
  print INFO "LLAMA_BRANCH:     ${LLAMA_BRANCH}"
  print INFO "LLAMA_COMMIT:     ${LLAMA_COMMIT}"
  print INFO "SOURCE_URL:       ${source_url}"
  print INFO "SOURCE_SHA256:    ${source_sha256}"
  print INFO "LLAMA_CODE_PATH:  ${LLAMA_CODE_PATH}"
  print INFO "LLAMA_PATCH:      ${LLAMA_PATCH}"
  print INFO "ROCM_ARCH:        ${ROCM_ARCH}"
  print INFO "ROCM_VERSION:     ${LLAMA_ROCM_VERSION}"
  print INFO "CMAKE_HIP_FLAGS:  ${LLAMA_CMAKE_HIP_FLAGS}"
  print INFO "CCACHE_MAXSIZE:   ${LLAMA_CCACHE_MAXSIZE}"
  print INFO "IS_RELEASE:       ${LLAMA_IS_RELEASE}"

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
    --build-arg ROCM_IMAGE="${LLAMA_BASE_IMAGE}"
    --build-arg ROCM_ARCH="${ROCM_ARCH}"
    --build-arg LLAMACPP_REPO="${LLAMA_REPO}"
    --build-arg LLAMACPP_BRANCH="${LLAMA_BRANCH}"
    --build-arg LLAMACPP_COMMIT="${LLAMA_COMMIT}"
    --build-arg LLAMACPP_SOURCE_URL="${source_url}"
    --build-arg LLAMACPP_SOURCE_SHA256="${source_sha256}"
    --build-arg LLAMACPP_CODE_PATH="${LLAMA_CODE_PATH}"
    --build-arg LLAMACPP_PATCH="${LLAMA_PATCH}"
    --build-arg CMAKE_HIP_FLAGS="${LLAMA_CMAKE_HIP_FLAGS}"
    --build-arg CCACHE_MAXSIZE="${LLAMA_CCACHE_MAXSIZE}"
    --progress plain
    --target final
    --file ./build-image.Dockerfile
    --pull
  )

  if [ "$LLAMA_PUSH" == "1" ]; then
    DOCKER_EXTRA_ARGS+=(--push)
  fi

  mkdir -p ./logs
  print INFO "Build llama.cpp"
  docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
}

build_dispatch check build "$@"
