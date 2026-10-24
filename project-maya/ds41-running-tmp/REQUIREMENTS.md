# Deepseek 4.1 requirements

- vision: on
- ctx limit: `192 * 1024`
- Long validation requests: **65536 tokens (64K)**, user-approved 2026-10-25.
  Do not run the prepared 128K/194K cases; retain them only as historical inputs.
  This reduces test duration, not the server's allocated context capacity.
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
- Original baseline: `docker.io/mixa3607/maya-gfx906:v1.1.26-rocm-10.1`.
- User-built comparison image: `docker.io/mixa3607/maya-gfx906:v1.1.27-rocm-10.1`,
  index digest `sha256:d46312703b79af1cd70174ae9ef2faee23875db9c51f90353424aba6101ac2c1`.
  A separate test pod and sequential GPU comparison were approved on 2026-10-25.
- Custom builds still require a separately agreed plan.

# Известные особенности по llama.cpp
- best cpu perf
  - prefill: 56 threads
  - decode: 48 threads
- best gpu perf
  - batch/ubatch: 2048
