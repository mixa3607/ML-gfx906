#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

IMAGE_TAGS=(
  "$PATCHED_ROCM_IMAGE:${ROCM_VERSION}-complete"
  "$PATCHED_ROCM_IMAGE:${ROCM_VERSION}-${REPO_GIT_REF}-complete"
)

if docker_image_pushed ${IMAGE_TAGS[0]}; then
  echo "${IMAGE_TAGS[0]} already in registry. Skip"
  exit 0
fi

for (( i=0; i<${#IMAGE_TAGS[@]}; i++ )); do
  IMAGE_TAGS[$i]="-t ${IMAGE_TAGS[$i]}"
done

docker buildx build ${IMAGE_TAGS[@]} --push \
  --build-arg BASE_ROCM_IMAGE=$BASE_ROCM_REGISTRY/rocm/dev-ubuntu-24.04:${ROCM_IMAGE_VER}-complete \
  --build-arg ROCM_ARCH=$ROCM_ARCH \
  --target final -f ./rocm.Dockerfile --progress=plain ./submodules
