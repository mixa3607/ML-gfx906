#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

PIP_NO_CACHE_DIR=1 python - <<'PY'
import setup

setup.pip_install(
    setup.PY_PACKAGES + [
        'tokenizers',
        'huggingface_hub',
        'safetensors',
        './third_party/llama.cpp/gguf-py',
    ],
    'Python dependencies',
)
PY
