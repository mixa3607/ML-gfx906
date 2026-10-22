#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

# Upstream setup installs PY_PACKAGES, plus tokenizers for DeepSeek's pack.
# Preinstalling the same list keeps setup and serve from reaching PyPI.
PIP_NO_CACHE_DIR=1 python - <<'PY'
import setup

setup.pip_install(setup.PY_PACKAGES + ['tokenizers'], 'Python dependencies')
PY
