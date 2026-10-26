#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya
cache=/root/.cache/huggingface/hub
model=$cache/models--unsloth--DeepSeek-V4.1-Flash-1017-GGUF/snapshots/60ad3651641b5c97679c807e064ab1d7a3ca1455/UD-Q8_K_XL
draft=$cache/models--peasantsmith--DeepSeek-V4.1-Flash-1017-Maya-GGUF/snapshots/d1fc01009f21e26157acb6858c315d0365483b72/dspark
test -f "$draft/dspark.bin"
test -f "$draft/dspark.json"
test -f /existing/vision/vision.bin
test -f /existing/vision/vision.json
test -f /data/screen/seed-profile.bin
printf '%s  %s\n' bcfd7697fc070b0ebcb0138c0ef029429ea0d4ff81ca60eeb7804e08efd0cd29 /data/screen/seed-profile.bin | sha256sum -c -
sha256sum "$draft/dspark.bin" "$draft/dspark.json"
# A regular private JSON index lets pack_gguf find its sibling BIN symlink.
mkdir /data/drafter
cp "$draft/dspark.json" /data/drafter/dspark.json
ln -s "$draft/dspark.bin" /data/drafter/dspark.bin
python tools/ds4/pack_gguf.py --model "$model" --out /data/ds4 \
  --vision /existing/vision --drafter /data/drafter/dspark.json
grep -c '^t mtp\.' /data/ds4/tensors.txt
