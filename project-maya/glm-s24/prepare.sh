#!/usr/bin/env bash
set -euo pipefail
cd /opt/maya

# Keep the cache read-only; GLM discovers the original shard names beside pack/.
snapshot="${HF_HOME:-/root/.cache/huggingface}/hub/models--peasantsmith--GLM-5.3-Flash-Maya-GGUF/snapshots/f16ee4ba50d8fd2bb726ea1862ca6ca14ba188da"
model=/data/glm-s24
template="${MAYA_CONFIG_TEMPLATE:-/etc/maya/maya-config.json}"
config="${MAYA_CONFIG:-/data/config/glm-s24.json}"
test -r "$template"
mkdir -p "$model/vision" "$(dirname "$config")"

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

for shard in 00001 00002 00003; do
  name="GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-${shard}-of-00003.gguf"
  link_file "$snapshot/Maya-S24/$name" "$model/$name"
done
for name in mmproj-GLM-5.3-Flash-F16.gguf GLM-5.3-Flash-vocab.gguf; do
  link_file "$snapshot/vision/$name" "$model/vision/$name"
done

stamp="$(cat SOURCE_COMMIT):glm-s24:f16ee4ba50d8fd2bb726ea1862ca6ca14ba188da:1"
if [[ ! -f "$model/.prepared" || "$(cat "$model/.prepared")" != "$stamp" ]] ||
   [[ ! -s "$model/pack/index.txt" || ! -s "$model/pack/native_experts.txt" ||
      ! -s "$model/pack/dense.bin" || ! -s "$model/pack/tokenizer/vocab.json" ||
      ! -s "$model/pack/tokenizer/chat_template.jinja" ]]; then
  export STRATA_GGUF_PY=/opt/maya/third_party/llama.cpp/gguf-py
  python tools/iq_pack.py \
    --gguf "$model/GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00001-of-00003.gguf" \
    --out "$model/pack" --compat-bf16
  if [[ ! -s "$model/pack/tokenizer/chat_template.jinja" ]]; then
    cp serve/glm5_chat_template.jinja "$model/pack/tokenizer/chat_template.jinja"
  fi
  printf '%s\n' "$stamp" > "$model/.prepared"
fi

# The server needs a writable config, even when its template is a ConfigMap.
cp "$template" "$config"
