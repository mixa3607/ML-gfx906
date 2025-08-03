#/bin/bash
set -e

cd $(dirname $0)
source ../env.sh

echo | docker buildx build --builder=remote \
  --build-arg BASE_ROCM_IMAGE=$BASE_ROCM_REGISTRY/rocm/dev-ubuntu-24.04:${ROCM_VERSION}-complete \
  --build-arg ROCM_ARCH=$ROCM_ARCH \
  -t $PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-${REPO_GIT_REF}-complete \
  -t $PATCHED_ROCM_REGISTRY/dev-ubuntu-24.04:${ROCM_VERSION}-complete \
  --target final -f ./rocm.Dockerfile --push --progress=plain $(mktemp -d)
