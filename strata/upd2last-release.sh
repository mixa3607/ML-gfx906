#!/bin/bash

RELEASE_TAG="$(curl -L \
  -H "Accept: application/vnd.github+json" \
  'https://api.github.com/repos/Niko1221/Strata/releases?per_page=1' | yq -r '.[0].tag_name')"

PRESET=preset.$RELEASE_TAG-rocm-7.14.sh
if ! [ -f "$PRESET" ]; then
  echo "Creating preset $PRESET"
  echo "#!/bin/bash

export STRATA_ROCM_VERSION='7.14'
export STRATA_REPO='https://github.com/Niko1221/Strata.git'
export STRATA_BRANCH='$RELEASE_TAG'
export STRATA_PRESET_NAME='$RELEASE_TAG-rocm-7.14'
export STRATA_PATCH='gfx906-setup.patch'
" > "$PRESET"
fi

echo "Check that build-context/patch/gfx906-setup.patch still applies to $RELEASE_TAG before building."
