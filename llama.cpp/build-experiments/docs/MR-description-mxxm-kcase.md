# Proposal: gfx906 K-quant MMQ tile overrides (Q4_K/Q5_K/Q6_K)

## Summary

Add per-format MMQ tile configurations for the K-quant types on gfx906
(Vega20 / MI50, wave64) in `ggml/src/ggml-cuda/mmq-config-gfx906.cuh`.

The mx-llama.cpp gfx906 config already handles Q8_0 (512 threads, J up to 128)
and MXFP4 (512 threads). This change adds the missing K-quant tuning measured
on MI50 with ROCm 7.14 and `-mllvm -amdgpu-sched-strategy=max-ilp`.

## Change

In `ggml/src/ggml-cuda/mmq-config-gfx906.cuh`, before the rdna2 fallback:

```cpp
CASE(GGML_TYPE_Q4_K, 256, 2, 128, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, true);
CASE(GGML_TYPE_Q4_K, 256, 2, 128, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, false);

CASE(GGML_TYPE_Q5_K, 256, 2,  64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, true);
CASE(GGML_TYPE_Q5_K, 256, 2,  64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q8_1, MMQ_ITER_K, false, false);

CASE(GGML_TYPE_Q6_K, 256, 2,  64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q6_K, MMQ_ITER_K, false, true);
CASE(GGML_TYPE_Q6_K, 256, 2,  64, 64, GGML_CUDA_MMQ_SRAM_LAYOUT_Q6_K, MMQ_ITER_K, false, false);
```

Same thread count, occupancy, J, K and stream-k as the rdna2 table. Only I
changes: I=128 -> I=64 for Q5_K and Q6_K. Q4_K stays at I=128.

## Motivation / measured effect

Direct A/B on the mx-llama.cpp tree (`751b611`), same compiler flag, one MI50,
`--n-prompt 2048 --ubatch-size 2048 --batch-size 2048 --n-gen 256`,
`--n-depth 0 --split-mode layer --flash-attn on`.

### End-to-end (tokens per second)

First the production GGUFs, then a full per-type matrix.

| Config | Qwen3.5-9B Q8_0 PP | Gemma-4-26B-A4B Q4_K_L PP |
| --- | ---: | ---: |
| mxxm stock (all K = I=128) | 1007.89 | 1365.99 |
| + these CASE overrides | 1006.80 (-0.1%) | **1428.77 (+4.6%)** |

Qwen PP is dominated by Q8_0 and is therefore unchanged. Gemma PP, which is
dominated by Q4_K/Q5_K/Q6_K, improves by 4.6%. TG is unchanged within noise.

Full per-type matrix (PP, same bench settings; models quantized from the same
F16 source with the mxxm `llama-quantize`):

| Type | Qwen stock | Qwen +case | delta | Gemma stock | Gemma +case | delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Q4_K_S | 906.99 | 915.19 | +0.9% | 1429.40 | 1432.62 | +0.2% |
| Q5_K_S | 552.38 | **659.87** | **+19.5%** | 1005.20 | **1150.46** | **+14.4%** |
| Q6_K | 545.05 | **766.48** | **+40.6%** | 1072.31 | **1397.02** | **+30.3%** |
| Q4_0 | 1127.98 | 1126.19 | -0.2% | - | - | - |
| Q4_1 | 1118.29 | 1116.14 | -0.2% | - | - | - |
| Q5_0 | 566.68 | 566.10 | -0.1% | - | - | - |
| Q5_1 | 553.88 | 554.53 | +0.1% | - | - | - |
| Q8_0 | 1005.19 | 1004.49 | -0.1% | 1622.31 | 1626.25 | +0.2% |
| IQ4_XS | 586.08 | 601.09 | +2.6% | - | - | - |
| IQ4_NL | 595.38 | 612.42 | +2.9% | - | - | - |

Non-K types are untouched, as expected. The K-quant gains reproduce on both a
9B dense model and a 26B MoE, and scale with model size.

### Kernel totals (Gemma PP, fallback=false)

| Kernel | stock | +override | delta |
| --- | ---: | ---: | ---: |
| Q4_K, J=64 | 1.959 s | 1.986 s | +1.4% (noise) |
| Q5_K, J=64 | 1.105 s | 0.931 s | **-15.7%** |
| Q6_K, J=64 | 0.631 s | 0.410 s | **-35.0%** |

I=64 halves the accumulator array (32 -> 16 floats per thread) and roughly
halves the X tile in LDS. On gfx906 this removes register pressure/scratch for
Q5_K and Q6_K without hurting their tile reuse. Q4_K was measured to lose ~53%
at I=64, so it keeps I=128.

## Why not upstream

The same tuning on the upstream tree at `360e134` improved Gemma PP from
1310.77 to 1362.88 (+4.0%) and is already the production configuration here.
This PR is against mx-llama.cpp so the existing Q8_0/MXFP4 work stays in one
place.

## Verification

- `MUL_MAT`: 1186/1186 passed.
- `MUL_MAT_ID`: 865/865 passed (MoE expert boundaries).
- Bit-exact: the change only alters tile geometry/thread mapping, not the
  accumulation math; all backend comparisons pass.

## Notes for reviewers

- Results were produced with ROCm 7.14 (AMD LLVM 23). gfx906 is GCN5/wave64
  and does not use the MFMA path, so these are dp4a kernels.
- The occupancy gate already in `mul_mat_q_switch_J` keeps the wide Q8_0 J=128
  tile away from MoE and row-sharded shapes; K-quants are J=64 everywhere.
- Private fork context: tuned for MI50 only, portability is not a goal.
