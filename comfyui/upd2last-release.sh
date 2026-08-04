RELEASE_TAG="$(curl -L \
  -H "Accept: application/vnd.github+json" \
  'https://api.github.com/repos/Comfy-Org/ComfyUI/releases?per_page=1' | yq -r '.[0].tag_name')"

PRESET=preset.$RELEASE_TAG-rocm-7.14.sh
if ! [ -f "$PRESET" ]; then
  echo "Creating preset $PRESET"
  echo "#!/bin/bash

export COMFYUI_ROCM_VERSION='7.14'
export COMFYUI_PYTORCH_VERSION='2.13.0'
export COMFYUI_BRANCH='$RELEASE_TAG'" > "$PRESET"
fi
