#!/usr/bin/env bash
set -euo pipefail
cd /opt/strata/terminal

# The Terminal launcher, entrypoint and healthcheck all look for the private
# runtime at <terminal>/python/bin/python3. Install the pinned dependencies
# there; the system Python stays untouched.
python3 -m venv python
python/bin/pip install --no-cache-dir -r requirements.txt -r requirements-monitor.txt
bin/strata --version
