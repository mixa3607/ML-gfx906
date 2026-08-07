# llama.cpp gfx906 (MI50) build experiments

Source-level tuning of llama.cpp MMQ for AMD Instinct MI50 (`gfx906`, wave64).
This directory only targets MI50; portability to other GPUs is not a goal.

## Environment

- llama.cpp upstream: commit `360e1349f0009c5ad99d21e3c4546b707addc68a` (b10288)
- mx-llama.cpp fork: commit `751b6114cdc6103efaedb94bace11e4ab8dc29be`
- ROCm 7.14 compiler: AMD clang 23.0.0git
- Compiler flag (mandatory): `-mllvm -amdgpu-sched-strategy=max-ilp`
- Device: 4x MI50, benchmarks use only `ROCm0`

## Layout

- `docs/` - investigation notes and sweep reports (see index below)
- `scripts/` - reproducible benchmark runners
- `results-20260806/` - scheduler check and first MMQ tile sweep artifacts
- `results-20260807/` - 512-thread Q8_0, mx-llama.cpp A/B, multi-type sweeps
- `stock-6.3.3/`, `stock-7.14/`, `tune1-7.14/`, `tune2-7.14/` - early bench txt
- `../build-context/patch/` - production and candidate source patches

## Docs index

| Doc | Content |
| --- | --- |
| `docs/gfx906-performance-playbook.md` | Methodology, bench/profiling loop |
| `docs/scheduler-check-20260806.md` | LLVM scheduler selection (max-ilp) |
| `docs/gfx906-mmq-sweep-20260806.md` | First MMQ tile sweep (I=64 for Q5_K/Q6_K) |
| `docs/gfx906-mmq-q8-512-sweep-20260807.md` | 512-thread Q8_0, J up to 128 |
| `docs/mxxm-kcase-ab-20260807.md` | K-quant CASE overrides on mx-llama.cpp |
| `docs/multi-type-sweep-qwen-20260807.md` | Qwen multi-type matrix |
| `docs/multi-model-multitype-sweep-20260807.md` | Qwen + Gemma multi-type matrix |
| `docs/MR-description-mxxm-kcase.md` | Ready-to-use PR description |
| `docs/gfx906-source-tuning-handoff.md` | Next experiments, quantization workflow |

## Patches

All patches apply to the llama.cpp tree at commit `360e134` (or the stated fork).

| Patch | Applied to | Effect |
| --- | --- | --- |
| `../build-context/patch/gfx906-mmq-i64.patch` | upstream | production config: Q8_0/Q5_K/Q6_K I=64, Q4_K I=128 |
| `../build-context/patch/gfx906-mmq-q8-512.patch` | upstream | Q8_0 512 threads, J 8..128 + occupancy gate, MXFP4 512 |
| `../build-context/patch/mxxm-gfx906-kcase.patch` | mx-llama.cpp | add Q4_K/Q5_K/Q6_K CASE to mx gfx906 config |
| `../build-context/patch/empty.patch` | any | no-op |

## Current production result

Built with `gfx906-mmq-i64.patch` + `max-ilp`, llama-bench 2048/256 tokens:

| Build | Qwen PP | Qwen TG | Gemma PP | Gemma TG |
| --- | ---: | ---: | ---: | ---: |
| ROCm 7.14 stock | 498.72 | 60.99 | 1193.46 | 87.65 |
| 7.14 max-ilp | 729.72 | 60.56 | 1310.77 | 86.52 |
| final MMQ patch + max-ilp | 735.41 | 60.75 | 1362.88 | 86.36 |
| Q8_0 512/J128 (candidate) | 985.86 | 60.70 | 1415.40 | 86.55 |

## Runners

```bash
scripts/run-scheduler-check.sh <source-dir> <results-dir> <stock|maxocc|maxilp|iterativeilp|maxilp-unroll100>
scripts/run-gfx906-mmq-sweep.sh <source-dir> <results-dir> <variant>
```

Both run inside the ROCm 7.14 container on the MI50 host. Each variant gets a
fresh build directory; artifacts (JSONL, rocprof, HSACO metadata, hashes) are
written to the results directory.
