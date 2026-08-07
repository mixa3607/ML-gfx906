# Qwen3.5-9B multi-type MMQ sweep: 2026-08-07

## Purpose

Expand the gfx906 K-quant CASE validation from the two production models to a
full quantization-type matrix on a single dense model, and answer which types
benefit from the Q4_K/Q5_K/Q6_K I overrides on the mx-llama.cpp base.

## Controlled configuration

- Source model: Qwen3.5-9B safetensors (rev c202236), converted to F16 GGUF
  with the mxxm `convert_hf_to_gguf.py`, then quantized with the mxxm
  `llama-quantize` (all from mx-llama.cpp `751b611`).
- mx-llama.cpp builds: `mxxm-stock` (as-is) vs `mxxm-kcase` (plus
  `CASE(Q4_K,256,2,128,64)`, `CASE(Q5_K,256,2,64,64)`, `CASE(Q6_K,256,2,64,64)`).
- ROCm 7.14, LLVM 23, `-mllvm -amdgpu-sched-strategy=max-ilp`
- One MI50, `ROCm0`, `--n-prompt 2048 --ubatch-size 2048 --batch-size 2048
  --n-gen 256 --n-depth 0 --split-mode layer --flash-attn on`

## Results (tokens per second)

| Type | stock PP | kcase PP | PP delta | stock TG | kcase TG |
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

PP samples per variant are stable (CV < 1%). TG is unchanged within noise for
every type.

## Interpretation

The K-quant overrides only move the `GGML_TYPE_Q*_K` kernels, so exactly the
K-types are affected:

- Q6_K: +40.6% PP (kernel 19.55 s -> 13.00 s, -33.5%; VGPR 128 -> 126, scratch
  56 B -> 0 B).
- Q5_K_S: +19.5% PP.
- Q4_K_S: +0.9% (I stays 128, expected no change; residual is run-to-run).
- Non-K types (Q4_0, Q4_1, Q5_0, Q5_1, Q8_0) are untouched.
- IQ4_XS/IQ4_NL show +2.6/+2.9% PP. These are 4-bit quants that do not hit
  `GGML_TYPE_Q4_K/Q5_K/Q6_K` kernels, so the small gain is likely compile
  variance rather than the override. Worth a re-run before claiming anything.

## Candidates for new CASE entries

The MXFP4 path already exists in mxxm. Two gaps remain for a dense Qwen:

1. Q4_K is the slowest 4-bit K-variant (906 PP) and is register-capped at 128
   VGPR. The handoff already notes Q4_K does not improve at I=64; a metadata
   load change is the candidate, not a tile change.
2. IQ4_XS/IQ4_NL PP is ~600, far below Q4_K/Q4_0. If IQ4 models become a
   target, they need their own specialization; the +2.6/+2.9% here is not
   enough to act on yet.

## Artifacts

- Raw JSONL per type: `results-20260807/types-{stock,kcase}/qwen-<TYPE>.jsonl`
- Q6_K rocprof: `results-20260807/types-{stock,kcase}/q6k-rocprof.log`
- Models: `/models/gfx906/Qwen3.5-9B-{F16,Q4_0,Q4_1,Q4_K_S,Q5_0,Q5_1,Q5_K_S,Q6_K,Q8_0,IQ4_XS,IQ4_NL}.gguf`
