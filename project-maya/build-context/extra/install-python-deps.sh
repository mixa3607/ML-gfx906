#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

# Upstream setup installs PY_PACKAGES, plus tokenizers for DeepSeek's pack.
# huggingface_hub provides the `hf` CLI used to fill the shared cache.
PIP_NO_CACHE_DIR=1 python - <<'PY'
import setup

setup.pip_install(
    setup.PY_PACKAGES + ['tokenizers', 'huggingface_hub'],
    'Python dependencies',
)
PY
