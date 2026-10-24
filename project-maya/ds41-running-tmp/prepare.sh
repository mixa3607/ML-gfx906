#!/usr/bin/env bash
set -euo pipefail

# Run inside the benchmark pod. The existing HF cache stays read-only.
cd /opt/maya
snapshot=/root/.cache/huggingface/hub/models--unsloth--DeepSeek-V4.1-Flash-1017-GGUF/snapshots/60ad3651641b5c97679c807e064ab1d7a3ca1455
vision=/root/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash-1017/snapshots/1bae0e1088993b9b82de08f59de5be5a34e42170
test ! -e /data/ds4
mkdir -p /data/vision /data/runs
ln -s "$vision/model-00001-of-00048.safetensors" /data/vision/
ln -s "$vision/config.json" /data/vision/
python tools/ds4/vision_pack.py --dir /data/vision
python tools/ds4/pack_gguf.py \
  --model "$snapshot/UD-Q8_K_XL" --out /data/ds4 --vision /data/vision
cp /opt/maya/data/expert-profile-ds4.bin /data/seed-profile.bin
cat /opt/maya/build-hip/MAYA-BUILD.json
