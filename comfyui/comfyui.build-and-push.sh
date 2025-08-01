source ../env.sh
echo | docker buildx build --builder=remote \
  --build-arg BASE_ROCM_IMAGE=$BASE_ROCM_REGISTRY/rocm/dev-ubuntu-24.04:${ROCM_VERSION}-complete \
  -t $PATCHED_COMFYUI_REGISTRY/comfyui:${COMFYUI_GIT_REF}-rocm-${ROCM_VERSION}-patch-${REPO_GIT_REF} \
  -t $PATCHED_COMFYUI_REGISTRY/comfyui:${COMFYUI_GIT_REF}-rocm-${ROCM_VERSION} \
  --target final -f ./comfyui.Dockerfile --push --progress=plain ./ComfyUI
