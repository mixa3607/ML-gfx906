#!/usr/bin/env bash
set -e

MODELS_PRESETS_DIR="${MODELS_PRESETS_DIR:-./server-profiles}"
MODELS_PRESETS_FILE="${LLAMA_ARG_MODELS_PRESET:-./server-profiles/presets.ini}"
echo "Try build presets.ini from $MODELS_PRESETS_DIR to $MODELS_PRESETS_FILE"
if python3 ./server-profiles/build-presets-ini.py --source-dir "$MODELS_PRESETS_DIR" --output "$MODELS_PRESETS_FILE"; then
  echo "Presets successfully builded"
  cat "$MODELS_PRESETS_FILE"
fi

exec ./tools.sh "$@"
