RELEASE_TAG="$(curl -L \
  -H "Accept: application/vnd.github+json" \
  'https://api.github.com/repos/Comfy-Org/ComfyUI/releases?per_page=1' | yq -r '.[0].tag_name')"

PRESET=preset.$RELEASE_TAG-cuda13.0-cudnn9.sh
if ! [ -f "$PRESET" ]; then
  echo "Creating preset $PRESET"
  echo "#!/bin/bash

export COMFYUI_CUDA_VERSION='cuda13.0-cudnn9'
export COMFYUI_PYTORCH_VERSION='2.11.0'
export COMFYUI_BRANCH='$RELEASE_TAG'" > "$PRESET"
fi
