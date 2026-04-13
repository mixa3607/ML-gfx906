#!/bin/bash
set -e

EXTRA_ARGS=()
EXTRA_ARGS+=("--enable-manager")

if [ "$PERSISTENCE_PATH" == "" ]; then
  echo "Warning: PERSISTENCE_PATH is not set. Persistence path init skip"
else
  echo "Copying data to persistence path"
  cp -r ./models ./custom_nodes ./input ./output "$PERSISTENCE_PATH"
  mkdir -p "$PERSISTENCE_PATH/user"
  mkdir -p "$PERSISTENCE_PATH/database"
  EXTRA_ARGS+=("--base-directory=$PERSISTENCE_PATH")
  EXTRA_ARGS+=("--database-url=sqlite:///$PERSISTENCE_PATH/database/comfyui.db")
fi

if [ "$VENV_NAME" != "" ]; then
  if [ "$PERSISTENCE_PATH" == "" ]; then
    VENV_ROOT="$PWD/$VENV_NAME"
    echo "Warning: PERSISTENCE_PATH is not set. Use $VENV_ROOT as venv root"
  else
    VENV_ROOT="$PERSISTENCE_PATH/$VENV_NAME"
    echo "Use $VENV_ROOT as venv root"
  fi

  echo "Creating venv in $VENV_ROOT"
  python3 -m venv "$VENV_ROOT"

  echo "Activating venv"
  source "$VENV_ROOT/bin/activate"
fi

if [ "$BOOTSTRAP_ONLY" == "1" ]; then
  echo "Warning: BOOTSTRAP_ONLY is set to 1. Just exit"
else
  echo "Run ComfyUI"
  exec python3 ./main.py "${EXTRA_ARGS[@]}" "$@"
fi
