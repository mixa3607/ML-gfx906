#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

cache="${HF_HOME:-/root/.cache/huggingface}/hub"
snapshot="$cache/models--peasantsmith--MiniMax-M3.1-Flash-Maya-GGUF/snapshots/9d256f59f1abe27216511c82e3a8bbe4bd0930d0/Maya-XS"
companions="$cache/models--Mia-AiLab--MiniMax-M3.1-Flash-EXL3-EAQ-v1-3.5-bpw/snapshots/fe796c40546d8b28340c5ed85b892e181ee21dec"
model=/data/minimax-xs
template="${MAYA_CONFIG_TEMPLATE:-/etc/maya/maya-config.json}"
config="${MAYA_CONFIG:-/data/config/minimax-xs.json}"
test -r "$template"
mkdir -p "$model" "$(dirname "$config")"

link_file() {
  local src="$1" dst="$2"
  test -s "$src"
  if [[ -e "$dst" || -L "$dst" ]]; then
    [[ -L "$dst" && "$(readlink -f "$dst")" == "$(readlink -f "$src")" ]] || {
      printf 'Refusing to replace %s\n' "$dst" >&2
      exit 1
    }
  else
    ln -s "$src" "$dst"
  fi
}

for shard in 00001 00002; do
  name="MiniMax-M3.1-Flash-Maya-XS-IQ1_S-${shard}-of-00002.gguf"
  link_file "$snapshot/$name" "$model/$name"
done
name=MiniMax-M3.1-Flash-Maya-XS-maya-indexers.bin
link_file "$snapshot/$name" "$model/$name"
for name in config.json preprocessor_config.json model-vision-00001-of-00001.safetensors \
    dspark/config.json dspark/model.safetensors.index.json dspark/model-dspark-00001.safetensors; do
  test -s "$companions/$name"
done

stamp="$(cat SOURCE_COMMIT):minimax-xs:9d256f59:fe796c40:1"
if [[ ! -f "$model/.prepared" || "$(cat "$model/.prepared")" != "$stamp" ]] ||
   [[ ! -s "$model/pack/mm3.txt" || ! -s "$model/pack/tensors.txt" ||
      ! -s "$model/pack/tokenizer/vocab.json" || ! -s "$model/pack/tokenizer/chat_template.jinja" ]]; then
  # Index the cached files in place, including vision and DSpark; no weight copy.
  python tools/mm3/pack_gguf.py --model "$model" --out "$model/pack" --companions "$companions"
  printf '%s\n' "$stamp" > "$model/.prepared"
fi

cp "$template" "$config"
