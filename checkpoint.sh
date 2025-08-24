#/bin/bash

source ./env.sh

if ! [ -z "$(git status --porcelain)" ]; then 
  echo "Workdir is dirty. Exit"
  exit 10
fi

TAG_NAME=$(git_get_current_tag)
if [ "$TAG_NAME" != "" ]; then
  TAG_NAME="$(date +%Y%m%d%H%M%S)"
  TAG_COMMENT="$(
    echo "Release $TAG_NAME"
    echo "Checkpoints:"
    echo "- ROCm: $ROCM_VERSION"
    echo "- ComfyUI: $COMFYUI_GIT_REF"
    echo "- llama.cpp: $LLAMA_GIT_REF"
  )"
  git tag -a "$TAG_NAME" -m "$TAG_COMMENT"
  echo -e "New tag $TAG_NAME:\n$TAG_COMMENT"
else
  echo "Commit already tagged with $TAG_NAME"
fi

git push origin "$TAG_NAME"
git push origin

pushd llama.cpp
./build-and-push.rocm.sh
./build-and-push.vulkan.sh
popd

pushd comfyui
./build-and-push.comfyui.sh
popd
