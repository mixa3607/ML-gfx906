#!/usr/bin/env bash
set -e

if [ "${MODELS_PRESETS_DIR}" != "" ]; then
  echo "WARNING: MODELS_PRESETS_DIR is deprecated; use M36_LLAMA_MODELS_PRESETS_DIR instead." >&2
  export M36_LLAMA_MODELS_PRESETS_DIR="${MODELS_PRESETS_DIR}"
fi
if [ "${MODELS_PRESETS_FILE}" != "" ]; then
  echo "WARNING: MODELS_PRESETS_FILE is deprecated; use M36_LLAMA_MODELS_PRESETS_FILE instead." >&2
  export M36_LLAMA_MODELS_PRESETS_FILE="${MODELS_PRESETS_FILE}"
fi

export M36_LLAMA_MODELS_PRESETS_DIR="${M36_LLAMA_MODELS_PRESETS_DIR:-./server-profiles}"
export M36_LLAMA_MODELS_PRESETS_FILE="${M36_LLAMA_MODELS_PRESETS_FILE:-${LLAMA_ARG_MODELS_PRESET:-./server-profiles/presets.ini}}"

echo "Try build presets.ini from $M36_LLAMA_MODELS_PRESETS_DIR to $M36_LLAMA_MODELS_PRESETS_FILE"
if python3 ./server-profiles/build-presets-ini.py --source-dir "$M36_LLAMA_MODELS_PRESETS_DIR" --output "$M36_LLAMA_MODELS_PRESETS_FILE"; then
  echo "Presets successfully builded"
  cat "$M36_LLAMA_MODELS_PRESETS_FILE"
  if [ "$M36_LLAMA_CHILD_WRAPPER" == "" ]; then
    export M36_LLAMA_CHILD_WRAPPER="/app/server-profiles/profiles-wrapper.py"
  fi
fi

if [ "$M36_LLAMA_CHILD_WRAPPER" != "" ]; then
  export LD_PRELOAD="/app/child-wrapper/spawn-hook.so${LD_PRELOAD:+:$LD_PRELOAD}"
  echo "ChildWrapper enabled! Used $M36_LLAMA_CHILD_WRAPPER"
fi

exec ./tools.sh "$@"
