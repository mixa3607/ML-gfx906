RELEASE_TAG="$(curl -L \
  -H "Accept: application/vnd.github+json" \
  'https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=1' | yq -r '.[0].tag_name')"

PRESET=preset.$RELEASE_TAG-rocm-6.3.3.sh
if ! [ -f "$PRESET" ]; then
  echo "Creating preset $PRESET"
  echo "#!/bin/bash

export LLAMA_ROCM_VERSION='6.3.3'
export LLAMA_BRANCH='$RELEASE_TAG'
export LLAMA_PRESET_NAME=\"\${LLAMA_BRANCH}-rocm-\${LLAMA_ROCM_VERSION}\"
" > "$PRESET"
fi

PRESET=preset.$RELEASE_TAG-rocm-7.2.1.sh
if ! [ -f "$PRESET" ]; then
  echo "Creating preset $PRESET"
  echo "#!/bin/bash

export LLAMA_ROCM_VERSION='7.2.1'
export LLAMA_BRANCH='$RELEASE_TAG'
export LLAMA_PRESET_NAME=\"\${LLAMA_BRANCH}-rocm-\${LLAMA_ROCM_VERSION}\"
" > "$PRESET"
fi
