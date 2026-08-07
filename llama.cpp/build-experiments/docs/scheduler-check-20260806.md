# Scheduler Check: 2026-08-06

## Purpose

Test whether LLVM 23 scheduler selection, rather than the ROCm runtime alone,
explains the 7.14 prompt-processing regression on gfx906.

## Controlled configuration

- llama.cpp: `360e1349f0009c5ad99d21e3c4546b707addc68a`
- Device: one `gfx906` MI50, `ROCm0`
- `--n-prompt 2048 --ubatch-size 2048 --batch-size 2048 --n-gen 256`
- `--n-depth 0 --split-mode layer --flash-attn on`
- Models: Qwen3.5-9B Q8_0 and Gemma-4-26B A4B Q4_K_L

## Variants

| Name | `CMAKE_HIP_FLAGS` |
| --- | --- |
| `stock` | _(empty)_ |
| `maxocc` | `-mllvm -amdgpu-sched-strategy=iterative-maxocc` |
| `maxilp` | `-mllvm -amdgpu-sched-strategy=max-ilp` |
| `iterativeilp` | `-mllvm -amdgpu-sched-strategy=iterative-ilp` |
| `maxilp-unroll100` | `max-ilp` plus `-unroll-threshold=100` |

## Execution

`run-scheduler-check.sh` configures a fresh build directory for each variant,
preserves CMake and compile commands, hashes `libggml-hip.so`, records the
environment, and writes raw `llama-bench` JSONL plus rocprof kernel summaries.
It makes no source changes to llama.cpp.

## Results

- `stock-preflight`: stopped before configuration because the runtime image has
  no `cmake`. Environment capture is preserved; no build or benchmark ran.

| Variant | Qwen PP | Qwen TG | Gemma PP | Gemma TG |
| --- | ---: | ---: | ---: | ---: |
| ROCm 6.3.3 stock reference | 751.69 | 55.83 | 1310.22 | 80.14 |
| 7.14 stock | 498.72 | 60.99 | 1193.46 | 87.65 |
| 7.14 `maxocc` | 731.40 | 61.36 | 316.25 | 87.28 |
| 7.14 `maxilp` | 729.72 | 60.56 | 1310.77 | 86.52 |
| 7.14 `maxilp-unroll100` | 730.30 | 60.87 | 1308.61 | 86.25 |

`maxilp` restores PP to within `-2.9%` for Qwen and `+0.0%` for Gemma
against the 6.3.3 reference, while retaining a `+8.5%` and `+8.0%` TG gain,
respectively. It is the candidate to package for 7.14.

`maxilp-unroll100` is rejected. Its Qwen results are within `0.5%` of
`maxilp`, while Gemma PP and TG are `0.2%` and `0.3%` lower. Its profile is
also indistinguishable at the hot kernels, so the additional unroll override
does not justify adding a second production compiler flag.

## Kernel attribution

`rocprofv3` attributes the PP difference to custom ggml `mul_mat_q` kernels,
not rocBLAS.

| Workload | Kernel specialization | 7.14 stock total | `maxocc` total | `maxilp` total |
| --- | --- | ---: | ---: | ---: |
| Qwen | `ggml_type=8` | 21.50 s | 13.87 s | 13.75 s |
| Gemma | `ggml_type=12` | 2.28 s | 17.48 s | 1.95 s |
| Gemma | `ggml_type=13` | 1.11 s | 5.82 s | 1.11 s |
| Gemma | `ggml_type=14` | 0.64 s | 6.03 s | 0.63 s |

`iterative-maxocc` is rejected: it helps Qwen's Q8 specialization but makes
Gemma's Q4_K variants 5.4-5.8 times slower. `max-ilp` improves both sets of
specializations and therefore needs no source-level per-kernel override.

## Artifacts

Raw benchmark JSONL, profiles, CMake cache, compilation commands, compiler and
runtime metadata are in `results-20260806/{stock,maxocc,maxilp,maxilp-unroll100}/`.
The setup and the failed preflight are preserved in `results-20260806/setup/`
and `results-20260806/stock-preflight/`.

## Follow-up

`iterative-ilp` is rejected: the package LLVM 23 crashes in greedy register
allocation on `flash_attn_tile` template instantiations. The build log is kept
in `results-20260806/iterativeilp/`; no benchmark ran. Do not test GFX11-only
`s_delay_alu` or VOPD flags on MI50.

Keep `max-ilp` as the 7.14 production flag. Any further scheduler trial must
use a fresh build and both model families, because `iterative-maxocc` shows a
single quantization format is not representative.
