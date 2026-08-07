## Bench

```bash
curl https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -L -o /usr/local/bin/yq && chmod +x /usr/local/bin/yq

./llama-bench \
  --hf-repo unsloth/Qwen3.5-9B-GGUF:Q8_0 --flash-attn 1 \
  --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
  --n-gen 256 --n-depth 0,16384,32768 --split-mode layer,tensor \
  --device rocm0,rocm0/rocm1,rocm0/rocm1/rocm2/rocm3 \
  --output jsonl | tee "qwen.txt" | yq -p=json
./llama-bench \
  --hf-repo bartowski/google_gemma-4-26B-A4B-it-GGUF:Q4_K_L --flash-attn 1 \
  --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
  --n-gen 256 --n-depth 0,16384,32768 --split-mode layer,tensor \
  --device rocm0,rocm0/rocm1,rocm0/rocm1/rocm2/rocm3 \
  --output jsonl | tee "gemma1.txt" | yq -p=json
./llama-bench \
  --hf-repo bartowski/google_gemma-4-26B-A4B-it-GGUF:Q6_K --flash-attn 1 \
  --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
  --n-gen 256 --n-depth 0,16384,32768 --split-mode tensor \
  --device rocm0,rocm0/rocm1/rocm2/rocm3 \
  --output jsonl | tee "gemma2.txt" | yq -p=json
./llama-bench \
  --hf-repo unsloth/gemma-4-31B-it-GGUF:Q8_K_XL --flash-attn 1 \
  --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
  --n-gen 256 --n-depth 0,16384,32768 --split-mode tensor \
  --device rocm0/rocm1/rocm2/rocm3 \
  --output jsonl | tee "gemma3.txt" | yq -p=json
```

