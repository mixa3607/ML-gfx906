#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source ../env.sh "llama.cpp-multiruntime"

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

declare -A IMAGE_ANNOTATIONS
IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/llama.cpp-multiruntime"
IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="Llama.cpp multiruntime"
IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${LLAMA_ROCM_IMAGE}"
IMAGE_ANNOTATIONS["org.opencontainers.image.cuda.base.name"]="${LLAMA_CUDA_IMAGE}"

echo "Start building llama.cpp multiruntime image..."
echo "ROCM_IMAGE:     ${LLAMA_ROCM_IMAGE}"
echo "CUDA_IMAGE:     ${LLAMA_CUDA_IMAGE}"
echo "IS_RELEASE:     ${LLAMA_IS_RELEASE}"

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  echo "TAG:          ${IMAGE_TAGS[$i]}"
  DOCKER_EXTRA_ARGS+=("--tag" "${IMAGE_TAGS[$i]}")
done
for key in "${!IMAGE_ANNOTATIONS[@]}"; do
  echo "ANNOTATION:   ${key}: ${IMAGE_ANNOTATIONS[$key]}"
  DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
done

if docker_image_pushed "${IMAGE_TAGS[0]}"; then
  echo -n "${IMAGE_TAGS[0]} already in registry. "
  if [ "$LLAMA_FORCE_BUILD" == "1" ]; then
    echo "Force build..."
  else
    echo "Skip."
    exit 0
  fi
fi

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
echo "Build llama.cpp multiruntime"
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" ./build-context 2>&1 | tee "./logs/build_$(date +%Y%m%d%H%M%S).log"
