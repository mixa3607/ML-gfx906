#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-complete"
  "$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-${REPO_GIT_REF}-complete"
  "$PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:latest-complete"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

echo | docker buildx build ${IMAGE_TAGS[@]/#/-t } \
  --build-arg BASE_ROCM_IMAGE=$BASE_ROCM_REGISTRY/rocm/dev-ubuntu-24.04:${ROCM_VERSION}-complete \
  --build-arg ROCM_ARCH=$ROCM_ARCH \
  --target final -f ./rocm.Dockerfile --push --progress=plain $(mktemp -d)
