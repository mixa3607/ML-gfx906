#/bin/bash
set -eo pipefail

cd $(dirname $0)
source ../env.sh "rocm"

echo "Start building ROCm image..."
echo "ROCM_VERSION: ${ROCM_VERSION}"
echo "ROCM_BUILD:   ${ROCM_BUILD}"

IMAGE_TAGS=(
  "$ROCM_IMAGE:${ROCM_VERSION}-complete-${REPO_GIT_REF}"
  "$ROCM_IMAGE:${ROCM_VERSION}-complete"
)

declare -A IMAGE_ANNOTATIONS
IMAGE_ANNOTATIONS["org.opencontainers.image.created"]="$(date --rfc-3339=seconds)"
IMAGE_ANNOTATIONS["org.opencontainers.image.authors"]="mixa3607"
IMAGE_ANNOTATIONS["org.opencontainers.image.source"]="https://github.com/mixa3607/ML-gfx906/tree/${REPO_GIT_REF}/rocm"
IMAGE_ANNOTATIONS["org.opencontainers.image.version"]="${REPO_GIT_REF}"
IMAGE_ANNOTATIONS["org.opencontainers.image.title"]="ROCm gfx906"
IMAGE_ANNOTATIONS["org.opencontainers.image.base.name"]="${ROCM_BASE_IMAGE}"

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo -n "${IMAGE_TAGS[0]} already in registry. "
  if [ "$ROCM_FORCE_BUILD" == "1" ]; then
    echo "Force build..."
  else
    echo "Skip."
    exit 0
  fi
fi

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  echo "TAG:          ${IMAGE_TAGS[$i]}"
  DOCKER_EXTRA_ARGS+=("--tag" "${IMAGE_TAGS[$i]}")
done
for key in "${!IMAGE_ANNOTATIONS[@]}"; do
  echo "ANNOTATION:   ${key}: ${IMAGE_ANNOTATIONS[$key]}"
  DOCKER_EXTRA_ARGS+=("--annotation" "${key}=${IMAGE_ANNOTATIONS[$key]}")
done

mkdir -p ./logs || true
docker buildx build "${DOCKER_EXTRA_ARGS[@]}" --push \
  --build-arg ROCM_BASE_IMAGE="${ROCM_BASE_IMAGE}" \
  --build-arg ROCM_BUILD="${ROCM_BUILD}" \
  --target final -f ./rocm.Dockerfile --progress=plain ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
