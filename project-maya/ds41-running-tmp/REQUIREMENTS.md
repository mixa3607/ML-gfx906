# Deepseek 4.1 requirements

- vision: on
- ctx limit: `192 * 1024`
- Preserve model computations and the full context. Ordinary floating-point
  and adaptive-cache differences are acceptable; identical logits/text are not
  required (user-approved revision, 2026-10-25).
- Allowed: RAM copies, NUMA, threads, chunk and separately validated flow/pump;
  dependency-safe YOCO1 may be evaluated with the default retention calculation.
- Forbidden: disk expert skipping (including AUTO), YOCO2, reduced YOCO_KEEP,
  extra requantization, and truncating context/history. YOCO1 must pass actual
  long-context checks before recommendation, not merely a short speed test.
- host mem limit: 192Gi
- model: `unsloth/DeepSeek-V4.1-Flash-1017-GGUF:UD-Q8_K_XL`
- dspark speculative: off
- gpu: 4x instinct mi50 32g

## Image
Сейчас есть `docker.io/mixa3607/maya-gfx906:v1.1.26-rocm-10.1`. Можно использовать его или по согласованию собрать кастомные версии в приватный registry.

# Известные особенности по llama.cpp
- best cpu perf
  - prefill: 56 threads
  - decode: 48 threads
- best gpu perf
  - batch/ubatch: 2048
