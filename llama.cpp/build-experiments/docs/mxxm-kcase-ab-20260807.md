# mxxm vs mxxm+kcase A/B: 2026-08-07

## Purpose

Answer directly whether the measured Q4_K/Q5_K/Q6_K tile overrides add anything
on top of the mx-llama.cpp gfx906 config, which already has 512-thread Q8_0
(J up to 128) and 512-thread MXFP4 plus the occupancy gate.

## Controlled configuration

- mx-llama.cpp: `751b6114cdc6103efaedb94bace11e4ab8dc29be`
  (the only commit visible in the depth-1 clone; tree differs slightly from
  upstream `360e134`, mmq.cuh is 1616 vs 1597 lines)
- ROCm 7.14, LLVM 23, target `gfx906`
- Compiler flag: `-mllvm -amdgpu-sched-strategy=max-ilp`
- Device: one MI50, `ROCm0`
- `--n-prompt 2048 --ubatch-size 2048 --batch-size 2048 --n-gen 256`
- `--n-depth 0 --split-mode layer --flash-attn on`
- Models: Qwen3.5-9B Q8_0 and Gemma-4-26B A4B Q4_K_L

## Variants

- `mxxm-stock`: mx-llama.cpp as-is (Q8_0 512/2/128/J8..128, MXFP4 512, gate;
  K-quants use the rdna2 fallback table, all I=128).
- `mxxm-kcase`: the same plus
  `CASE(Q4_K, 256, 2, 128, 64)`, `CASE(Q5_K, 256, 2, 64, 64)`,
  `CASE(Q6_K, 256, 2, 64, 64)` (fallback true/false), which is the entire diff.

## End-to-end results

Values are tokens per second.

| Variant | Qwen PP | Qwen TG | Gemma PP | Gemma TG |
| --- | ---: | ---: | ---: | ---: |
| mxxm-stock | 1007.89 | 63.36 | 1365.99 | 87.84 |
| mxxm-kcase | 1006.80 | 63.44 | **1428.77** | 88.04 |
| delta | -0.1% | +0.1% | **+4.6%** | +0.2% |

Qwen is unchanged: its PP time is dominated by the Q8_0 kernel, which is
identical in both configs. Gemma gains +4.6% PP, coming entirely from the
Q5_K/Q6_K I=64 overrides.

## Kernel attribution (Gemma Q4_K_L PP)

`mul_mat_q` fallback=false totals for the K-quant specializations:

| Kernel | mxxm-stock | mxxm-kcase | delta |
| --- | ---: | ---: | ---: |
| Q4_K (type 12), J=64 | 1.959 s | 1.986 s | +1.4% (noise) |
| Q5_K (type 13), J=64 | 1.105 s | 0.931 s | **-15.7%** |
| Q6_K (type 14), J=64 | 0.631 s | 0.410 s | **-35.0%** |

The Q4_K kernel is unchanged, as intended (I stays 128). The Q5_K and Q6_K
kernels reproduce the same ~15-35% gains measured on the upstream tree on
2026-08-06.

## Conclusion

The K-quant CASE overrides add a real +4.6% Gemma PP on top of mx-llama.cpp,
with no Qwen or TG regression. They are orthogonal to the mxxm Q8_0/MXFP4 work
and combine with it additively.

## Artifacts

- Patch: `build-context/patch/mxxm-gfx906-kcase.patch`
- Local clone with applied branch: `mmq-config-profiling/mx-llama-cpp`
  (branch `gfx906-kcase`)
- Raw results: `results-20260807/{mxxm-stock,mxxm-kcase}/`
