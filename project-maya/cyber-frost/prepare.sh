#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

snapshot="${HF_HOME:-/root/.cache/huggingface}/hub/models--peasantsmith--CYBER-FROST-3.8-PS-GUFF/snapshots/32867bb9e228afac427c136dd657b34b7c3f0e86"
model=/data/cyber-frost
name=CYBER-FROST-3.8-PS-GUFF-Q5_K_M.gguf
template="${MAYA_CONFIG_TEMPLATE:-/etc/maya/maya-config.json}"
config="${MAYA_CONFIG:-/data/config/cyber-frost.json}"
test -r "$template"
test -s "$snapshot/$name"
mkdir -p "$model" "$(dirname "$config")"
if [[ -e "$model/$name" || -L "$model/$name" ]]; then
  [[ -L "$model/$name" && "$(readlink -f "$model/$name")" == "$(readlink -f "$snapshot/$name")" ]] || {
    printf 'Refusing to replace %s\n' "$model/$name" >&2
    exit 1
  }
else
  ln -s "$snapshot/$name" "$model/$name"
fi

stamp="$(cat SOURCE_COMMIT):cyber-frost:32867bb9e228afac427c136dd657b34b7c3f0e86:1"
if [[ ! -f "$model/.prepared" || "$(cat "$model/.prepared")" != "$stamp" ]] ||
   [[ ! -s "$model/pack/index.txt" || ! -s "$model/pack/native_experts.txt" ||
      ! -s "$model/pack/dense.bin" || ! -s "$model/pack/tokenizer/vocab.json" ||
      ! -s "$model/pack/mtp/dense.txt" || ! -s "$model/pack/mtp/experts.bin" ]]; then
  export STRATA_GGUF_PY=/opt/maya/third_party/llama.cpp/gguf-py
  python tools/iq_pack.py --gguf "$model/$name" --out "$model/pack" --compat-bf16
  # Upstream requires an MTP pack even when drafting is disabled at runtime.
  python tools/mtp_from_gguf.py --gguf "$model/$name" --out "$model/pack/mtp"
  printf '%s\n' "$stamp" > "$model/.prepared"
fi
if [[ ! -s "$model/pack/expert-profile.bin" ]]; then
  cp data/expert-profile-qwen.bin "$model/pack/expert-profile.bin"
fi

cp "$template" "$config"
