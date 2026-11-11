#!/bin/sh
# gfx906 image entry: this image is HIP only. Before the upstream entrypoint
# starts `strata launch`, stamp a run config that is already on the volume so
# the monitor reads amdgpu sysfs (backend hip) and the cards named by GPUS.
# GPUS=0,1 -> "gpu": [0, 1]. GPUS=0 -> "gpu": 0. Empty or all leaves gpu alone.
# A config launch has not written yet is created by setup on this HIP image.
set -u

export STRATA_ENGINE_BACKEND=hip

python3 - <<'PY'
import json
import os
from pathlib import Path

raw = (os.environ.get("GPUS") or os.environ.get("GPU") or "").replace(" ", "")
gpu = None
if raw and raw.lower() != "all":
    parts = [p for p in raw.split(",") if p]
    if parts and all(p.isdigit() for p in parts):
        nums = [int(p) for p in parts]
        gpu = nums[0] if len(nums) == 1 else nums

override = os.environ.get("STRATA_HIP_CONFIG_DIRS")
if override:
    roots = [Path(p) for p in override.split(":") if p]
else:
    state = Path(os.environ.get("XDG_STATE_HOME") or "/data/state")
    roots = [Path("/data/install"), state / "strata" / "launch"]

for root in roots:
    if not root.is_dir():
        continue
    for path in sorted(root.glob("*.json")):
        if path.name.endswith((".choices.json", ".tune.json")):
            continue
        try:
            cfg = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        if not isinstance(cfg, dict) or ("exe" not in cfg and "args" not in cfg):
            continue
        changed = False
        if cfg.get("backend") != "hip":
            cfg["backend"] = "hip"
            changed = True
        if gpu is not None and cfg.get("gpu") != gpu:
            cfg["gpu"] = gpu
            changed = True
        if not changed:
            continue
        mode = path.stat().st_mode & 0o777
        path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.chmod(path, mode)
        shown = "unchanged" if gpu is None else json.dumps(gpu)
        print(f"gfx906: {path} backend=hip gpu={shown}", flush=True)
PY

exec /opt/strata/terminal/docker/entrypoint.sh "$@"
