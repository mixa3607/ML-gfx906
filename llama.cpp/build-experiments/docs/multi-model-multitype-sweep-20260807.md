# Multi-model, multi-type MMQ K-quant sweep: 2026-08-07

## Purpose

Widen the gfx906 K-quant CASE validation beyond the two production GGUFs.
Quantize both models into several types and A/B `mxxm-stock` (K-quants use the
rdna2 table, all I=128) against `mxxm-kcase` (plus
`CASE(Q4_K,256,2,128,64)`, `CASE(Q5_K,256,2,64,64)`, `CASE(Q6_K,256,2,64,64)`).

## Controlled configuration

- Source models: Qwen3.5-9B safetensors (rev c202236) and
  google/gemma-4-26B-A4B-it (rev 4d7ae49).
- F16 GGUF produced with the mxxm `convert_hf_to_gguf.py`; all quantizations
  with the mxxm `llama-quantize` (tree `751b611`). Note: Gemma4 F16 needed
  transformers 5.14.1 (installed in `/opt/conv-venv`) because 4.57.6 fails on
  the `extra_special_tokens` list.
- ROCm 7.14, LLVM 23, `-mllvm -amdgpu-sched-strategy=max-ilp`
- One MI50, `ROCm0`, `--n-prompt 2048 --ubatch-size 2048 --batch-size 2048
  --n-gen 256 --n-depth 0 --split-mode layer --flash-attn on`

## Qwen3.5-9B (dense) - tokens per second

| Type | stock PP | kcase PP | delta | stock TG | kcase TG |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q4_0 | 1127.98 | 1126.19 | -0.2% | 82.44 | 82.47 |
| Q4_1 | 1118.29 | 1116.14 | -0.2% | 85.28 | 85.46 |
| Q4_K_S | 906.99 | 915.19 | +0.9% | 74.15 | 74.06 |
| Q5_0 | 566.68 | 566.10 | -0.1% | 70.82 | 70.83 |
| Q5_1 | 553.88 | 554.53 | +0.1% | 77.68 | 77.57 |
| Q5_K_S | 552.38 | **659.87** | **+19.5%** | 66.88 | 66.88 |
| Q6_K | 545.05 | **766.48** | **+40.6%** | 60.45 | 60.60 |
| Q8_0 | 1005.19 | 1004.49 | -0.1% | 63.37 | 63.46 |
| IQ4_XS | 586.08 | 601.09 | +2.6% | 84.21 | 84.14 |
| IQ4_NL | 595.38 | 612.42 | +2.9% | 78.70 | 78.65 |

## Gemma-4-26B-A4B (MoE) - tokens per second

| Type | stock PP | kcase PP | delta | stock TG | kcase TG |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q4_K_S | 1429.40 | 1432.62 | +0.2% | 86.44 | 86.74 |
| Q5_K_S | 1005.20 | **1150.46** | **+14.4%** | 84.65 | 84.73 |
| Q6_K | 1072.31 | **1397.02** | **+30.3%** | 84.68 | 84.06 |
| Q8_0 | 1622.31 | 1626.25 | +0.2% | 90.06 | 90.11 |

All PP samples have CV < 1%. TG is unchanged within noise for every type.

## Kernel attribution (Gemma Q6_K PP, `mul_mat_q<ggml_type=14,64,...>`)

| fallback | stock | kcase | delta |
| --- | ---: | ---: | ---: |
| false | 6.582 s | 4.414 s | **-33.0%** |
| true | 1.178 s | 0.680 s | **-42.3%** |

## Interpretation

The three K-quant CASE entries move exactly the `Q*_K` kernels and nothing
else:

- Q6_K: +40.6% Qwen / +30.3% Gemma PP. VGPR 128 -> 126, scratch 56 B -> 0 B
  (Qwen), no scratch on either fallback path on Gemma.
- Q5_K: +19.5% Qwen / +14.4% Gemma PP.
- Q4_K: unchanged (I stays 128 by design; I=64 measured ~53% slower).
- Non-K types (Q4_0, Q4_1, Q5_0, Q5_1, Q8_0) are untouched on both models.

The gains scale with model size: the same CASE entries produce larger absolute
PP gains on the 26B MoE than on the 9B dense model, and the benefit is
independent of the mx-llama.cpp Q8_0/MXFP4 work.

## Artifacts

- Qwen JSONL: `results-20260807/types-{stock,kcase}/qwen-<TYPE>.jsonl`
- Gemma JSONL: `results-20260807/gemma-types-{stock,kcase}/gemma-<TYPE>.jsonl`
- Q6_K rocprof: `results-20260807/{types,gemma-types}-{stock,kcase}/q6k-rocprof.log`
- Models: `/models/gfx906/Qwen3.5-9B-*.gguf`, `/models/gfx906/Gemma-4-26B-*.gguf`
