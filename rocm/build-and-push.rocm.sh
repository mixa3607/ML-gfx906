#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$PATCHED_ROCM_IMAGE:${ROCM_VERSION}-${REPO_GIT_REF}-complete"
  "$PATCHED_ROCM_IMAGE:${ROCM_VERSION}-complete"
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
  --build-arg BASE_ROCM_IMAGE="${BASE_ROCM_IMAGE}:${ROCM_IMAGE_VER}-complete" \
  --build-arg ROCM_ARCH="${ROCM_ARCH}" \
  --target final -f ./rocm.Dockerfile --progress=plain ./submodules 2>&1 | tee ./logs/build_$(date +%Y%m%d%H%M%S).log
