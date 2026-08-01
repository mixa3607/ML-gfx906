#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh "rocm"

IMAGE_TAGS=(
  "$ROCM_IMAGE:${ROCM_THEROCK_VERSION}-complete-${REPO_GIT_REF}"
  "$ROCM_IMAGE:${ROCM_THEROCK_VERSION}-complete"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

DOCKER_EXTRA_ARGS=()
for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  DOCKER_EXTRA_ARGS+=("-t" "${IMAGE_TAGS[$i]}")
done

mkdir ./logs || true
docker buildx build ${DOCKER_EXTRA_ARGS[@]} --push \
  --build-arg ROCM_BASE_IMAGE="${ROCM_BASE_IMAGE}" \
  --build-arg ROCM_ARCH="${ROCM_ARCH}" \
  --build-arg THEROCK_VERSION="${ROCM_THEROCK_VERSION}" \
  --target final -f ./rocm.Dockerfile --progress=plain ./build-context 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
