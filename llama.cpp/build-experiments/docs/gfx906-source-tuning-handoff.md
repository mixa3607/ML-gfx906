# gfx906 Source Tuning Handoff

## Goal

Continue source-level llama.cpp optimization for AMD Instinct MI50 (`gfx906`,
wave64) after recovering ROCm 7.14 prompt processing with LLVM scheduling and
a format-specific MMQ tile configuration.

This repository only targets MI50. Portability to other GPUs is not a goal.

## Fixed environment

- llama.cpp commit: `360e1349f0009c5ad99d21e3c4546b707addc68a`
- ROCm 6.3.3 reference compiler: AMD LLVM 18
- ROCm 7.14 compiler: AMD LLVM 23
- GPUs: four MI50, benchmarks use only `ROCm0`
- PP: prompt 2048, generation 0
- TG: prompt 0, generation 256
- Batch and ubatch: 2048
- `--n-depth 0 --split-mode layer --flash-attn on`
- Production compiler flag: `-mllvm -amdgpu-sched-strategy=max-ilp`

The reproducible scheduler work is in `scheduler-check-20260806.md`. The
source-level MMQ sweep is in `gfx906-mmq-sweep-20260806.md`.

## Current production result

| Build | Qwen PP | Qwen TG | Gemma PP | Gemma TG |
| --- | ---: | ---: | ---: | ---: |
| ROCm 7.14 stock | 498.72 | 60.99 | 1193.46 | 87.65 |
| 7.14 `max-ilp` | 729.72 | 60.56 | 1310.77 | 86.52 |
| 7.14 final MMQ patch + `max-ilp` | **735.41** | 60.75 | **1362.88** | 86.36 |

The source patch is `build-context/patch/gfx906-mmq-i64.patch`. It is applied
to the cloned llama.cpp tree during image construction.

Current J=64 gfx906 overrides:

| Format | Type number | Threads | I | J | Occupancy target |
| --- | ---: | ---: | ---: | ---: | ---: |
| Q8_0 | 8 | 256 | 64 | 64 | 2 |
| Q4_K | 12 | 256 | 128 | 64 | 2 |
| Q5_K | 13 | 256 | 64 | 64 | 2 |
| Q6_K | 14 | 256 | 64 | 64 | 2 |

All other types and J values use the upstream RDNA2 fallback.

The final build passed `1186/1186` `MUL_MAT` backend comparisons against CPU.

## Established technical findings

1. gfx906 is GCN5/wave64 but upstream routes it through
   `mmq-config-rdna2.cuh`.
2. The hot PP kernels are custom `mul_mat_q`, not rocBLAS.
3. gfx906 uses packed int8 dot products (`v_dot4_i32_i8`); it does not use the
   CDNA MFMA path.
4. The upstream J=64 RDNA2 configuration uses 256 threads, I=128, K=256,
   occupancy target 2, and no Stream-K.
5. I=128/J=64/256 threads gives 32 FP32 accumulators per thread.
6. Q8_0, Q5_K, and Q6_K use about 45-47 KiB LDS at I=128, allowing only one
   block per 64 KiB MI50 CU.
7. Q4_K uses about 29 KiB LDS but remains register/scratch constrained.
8. `max-ilp` improves instruction scheduling. It does not remove K-quant
   register pressure.
9. LLVM 23 `iterative-maxocc` creates 788-1012 B private segments for K-quants
   and causes 5-8x regressions.
10. I=64 halves the accumulator array to 16 floats per thread and roughly
    halves the X LDS tile.
11. I=64 improves Q8_0, Q5_K, and Q6_K, but makes Q4_K approximately 53%
    slower. Tile geometry must be selected per quantization format.
12. I=96 compiles but fails at runtime with
    `HSA_STATUS_ERROR_MEMORY_APERTURE_VIOLATION`. Existing static assertions
    do not express all indexing/layout requirements.

Measured J=64 non-fallback changes from I=128 to I=64:

| Format | Kernel change | Resource change |
| --- | ---: | --- |
| Q8_0 | about `-0.7%` | 119 to 71 VGPR, no scratch |
| Q4_K | about `+52.8%` | scratch 64 to 52 B, still 128 VGPR |
| Q5_K | about `-15.5%` | scratch 80 to 68 B, still 128 VGPR |
| Q6_K | about `-34.9%` | 128 to 126 VGPR, scratch 56 to 0 B |

## Next experiment: 512-thread Q8_0

A promising alternative is eight wave64 wavefronts in one Q8_0 block. Do not
replace the measured Q5_K/Q6_K overrides while testing Q8_0.

The proposed 512-thread config must not rely on the current J selector as an
occupancy gate. At commit `360e134`, `mul_mat_q_switch_J()` checks only whether
the config exists, fits the per-block LDS limit, and reduces
`ceil(ncols_max/J)`. If J=128 is exposed and fits LDS, it will normally be
selected for a 2048-column workload.

Approximate Q8_0 resources before compilation:

| Threads | I | J | Accumulators/thread | Dynamic LDS | Expected blocks/CU |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 256 | 64 | 64 | 16 | about 28 KiB | up to 2 |
| 512 | 128 | 64 | 16 | about 47 KiB | 1 |
| 512 | 128 | 128 | 32 | about 55 KiB | 1 |

The 512/I128/J64 case is the best first candidate. It keeps 16 accumulators per
thread and eight active waves, while avoiding the repeated Y load caused by
two separate I=64 blocks.

Test matrix:

| Variant | Threads | Occupancy | I | Exposed J |
| --- | ---: | ---: | ---: | --- |
| Current control | 256 | 2 | 64 | 64 |
| A | 512 | 1 | 128 | 64 only |
| B | 512 | 2 | 128 | 64 only |
| C | 256 | 2 | 128 | 128 only |
| D | 512 | 1 | 128 | 128 only |
| E | 512 | 2 | 128 | 128 only |

Start with occupancy 1 for 512-thread blocks. Dynamic LDS makes two such
blocks physically impossible, so `__launch_bounds__(512, 2)` may constrain
register allocation or create spills without increasing real residency.

Only after finding the best fixed J should multiple J values be exposed. If a
new selector gate is added, base it on total XY tile count versus CU count and
validate dense, tensor-sharded, and MoE shapes separately.

For each variant record:

- End-to-end Qwen PP/TG and Gemma PP/TG.
- rocprof kernel name, call count, total time, mean time, and selected J.
- VGPR, SGPR, private segment, wavefront size, and dynamic LDS.
- Both `fallback=false` and `fallback=true` resources.
- `test-backend-ops` correctness for `MUL_MAT` and `MUL_MAT_ID`.
- Dense and MoE behavior with final I/J tiles that are not exact multiples.

## Other source-level candidates

### Double-buffer Y

`mul_mat_q_process_tile()` currently uses four workgroup barriers per K=256
iteration:

1. Load X and Y0, barrier.
2. Dot Y0, barrier.
3. Load Y1, barrier.
4. Dot Y1, barrier.

Two Y buffers can load Y0 and Y1 before computation and reduce this to two
barriers. The additional Y buffer is about 9 KiB at J=64. Test this separately
from I=64 because combining both may prevent a second resident block.

Expected potential: approximately 5-15% kernel-level if barrier/LDS stalls are
significant. Verify with hardware counters before retaining it.

### Q4_K metadata path

Q4_K does not benefit from I=64. Investigate its scale/min metadata loads,
address generation, and wave64 lane duplication instead. Candidate changes:

- Load metadata once per lane pair and broadcast with a wave shuffle.
- Reduce duplicated scale/min unpacking.
- Check whether aligned metadata packets can use wider global loads.
- Inspect LDS bank conflicts before changing padding.

### Q5_K and Q6_K

I=64 already provides large gains. Possible follow-up work:

- Shorten metadata/unpack live ranges so Q5_K falls below 128 VGPR.
- Preserve Q6_K's zero-scratch result while testing loader vectorization.
- Test fallback geometry separately because edge tiles have higher scratch.

### Y global-to-LDS copy

The copy is coalesced but may compile to many scalar operations. Inspect ISA
before testing `int2`/`int4` loads and stores. Reject wider copies if they move
the kernel into a higher VGPR allocation tier.

### LDS layout

Only investigate padding or XOR swizzling after collecting LDS bank-conflict
counters. Existing padding is deliberate; an uninformed change can cause a
large regression.

### Persistent weight prepacking

Static K-quant weights are unpacked every invocation. Prepacking at model load
could remove repeated bit extraction, but costs VRAM and complicates cache,
multi-GPU, and model lifetime behavior. This is a longer-term redesign, not the
next experiment.

### MXFP4

MXFP4 is not used by the current Qwen Q8_0 or Gemma Q4_K_L workloads. Tune its
thread count only with an actual MXFP4 model or isolated synthetic matrices.
Do not infer MXFP4 performance from Q8_0.

## Quantization test strategy

Use three validation levels.

### 1. Synthetic matrices

Use `test-backend-ops` in correctness and perf modes with an explicitly
selected weight type and M/N/K shapes. This is the cleanest way to isolate one
`GGML_TYPE_Q*`, I/J selection, and fallback behavior.

Important dimensions include boundaries around 64 and 128:

- Output rows: 63, 64, 65, 127, 128, 129, 191, 192.
- Output columns: 7, 8, 9, 63, 64, 65, 127, 128, 129, and 2048.
- Several realistic K dimensions from the selected models.

Run both `MUL_MAT` and `MUL_MAT_ID`. The latter is required for MoE and expert
edge cases.

### 2. Mostly homogeneous GGUFs

Create one GGUF per target format from the same F16/BF16 source model:

- Q8_0
- Q4_K_S
- Q5_K_S
- Q6_K
- MXFP4 only if it is a real target workload

Standard quantization may intentionally keep embeddings, output, norms, or
small/incompatible tensors in another type. That is acceptable. The goal is
for the target format to dominate quantizable matrix weights, not to force
every tensor regardless of correctness or dimensional constraints.

Avoid `_M` and `_L` variants for isolated kernel tuning because they are mixed
quantizations. Keep them for production end-to-end validation.

Always inspect the resulting tensor-type histogram and confirm with rocprof
that the expected `mul_mat_q<(ggml_type)N,...>` kernel dominates. Do not rely
only on the quantization name.

Do not quantize an already quantized GGUF. Download F16/BF16 source weights or
an F16 GGUF, then generate every comparison variant from that same source.

### 3. Production GGUFs

Re-run the existing Qwen Q8_0 and Gemma Q4_K_L files. These mixed real-world
workloads determine whether an isolated kernel improvement is useful overall
and whether another format regresses.

## Model recommendations

### Minimum set

The same two model families are enough for the next tuning stage:

1. Qwen3.5-9B as the dense representative.
2. Gemma-4-26B-A4B as the MoE representative.

They already exercise the production paths and provide different matrix and
quantization mixes. Download the exact F16/BF16 source revisions corresponding
to the existing benchmark GGUFs, then convert them to a shared F16 GGUF before
creating the quantized variants.

For Qwen, use the source model corresponding to the current
`unsloth/Qwen3.5-9B-GGUF` artifact. For Gemma, use the source revision
corresponding to the current
`bartowski/google_gemma-4-26B-A4B-it-GGUF` artifact. Record source repository
and revision hashes; model revisions can change independently of names.

Recommended generated variants:

| Model | Required isolated variants | Existing production validation |
| --- | --- | --- |
| Qwen3.5-9B | Q8_0, Q4_K_S, Q5_K_S, Q6_K | current Q8_0 |
| Gemma-4-26B-A4B | Q4_K_S, Q5_K_S, Q6_K; Q8_0 if storage permits | current Q4_K_L |

Qwen is much cheaper to requantize and should be used for the complete format
matrix first. Gemma is most valuable for `MUL_MAT_ID`, expert boundaries, and
the final production check. If disk or conversion time is limited, do not make
every Gemma quant immediately.

Approximate temporary storage planning:

- A 9B BF16/F16 source is about 18 GB before conversion overhead.
- A 26B BF16/F16 source is about 50 GB before conversion overhead.
- Keep enough additional space for several 4-10 GB Qwen outputs and several
  15-30 GB Gemma outputs, plus Hugging Face cache duplication.

### Extended confidence set

Add these only after the two-model tuning converges:

1. A classic dense transformer such as Llama-3.1-8B-Instruct. This checks that
   gains are not specific to Qwen architecture or hidden dimensions.
2. A smaller open MoE such as OLMoE-1B-7B. This provides cheaper expert-count,
   token-distribution, and `MUL_MAT_ID` coverage than repeatedly quantizing the
   26B Gemma model.

These models improve generalization confidence but are not required to decide
whether a change helps this MI50 production workload.

## Acceptance criteria

Retain a change only when all conditions hold:

1. It passes backend correctness for affected operations and quant types.
2. It does not introduce HSA aperture violations or invalid edge-tile access.
3. The hot kernel improvement repeats across multiple runs and exceeds normal
   run-to-run noise.
4. Qwen and Gemma end-to-end PP do not regress outside noise.
5. TG remains within noise unless the change intentionally targets TG.
6. No affected specialization gains large private segments or scratch traffic.
7. Raw build, benchmark, profile, resource, and failure artifacts are saved.

## Recording requirements

Every experiment must preserve:

- Exact source patch and llama.cpp commit.
- Full CMake configure/build logs and compile commands.
- Compiler identity and HIP flags.
- `libggml-hip.so` hash and dependency list.
- Raw benchmark JSONL, including all individual samples.
- rocprof kernel summaries.
- HSACO VGPR/SGPR/private-segment metadata.
- Correctness output.
- Failed builds and runtime failures without reclassifying them as performance
  results.

Use a fresh build directory for every source/config variant. Never reuse an
old build directory after changing template configuration.

## Immediate next action

Preserve the current Q5_K/Q6_K I=64 and Q4_K I=128 settings. Run the fixed-J
Q8_0 512-thread matrix, beginning with:

```text
threads=512, occupancy=1, I=128, J=64
```

Compare it directly with the current 256-thread/I=64/J=64 Q8_0 kernel. Do not
enable J=128 or MXFP4 in the same first build, because that would conflate
thread count, tile width, selector behavior, and an unrelated quant format.

## DONE 2026-08-07: 512-thread Q8_0 sweep

Executed. Results in
`./gfx906-mmq-q8-512-sweep-20260807.md` and `results-20260807/`.

Best candidate `gfx906-mmq-q8-512.patch` (mx-llama.cpp style):
Q8_0 = 512 threads, occupancy 2, I=128, J exposed 8..128, plus the
`mul_mat_q_switch_J` occupancy gate (J<=64 for MoE and grids smaller than the
CU count). MXFP4 also routed to 512 threads. Q4_K=128 / Q5_K=64 / Q6_K=64
overrides unchanged.

| Build | Qwen PP | Qwen TG | Gemma PP | Gemma TG |
| --- | ---: | ---: | ---: | ---: |
| 7.14 final I=64 patch | 735.41 | 60.75 | 1362.88 | 86.36 |
| 512/1/128/64 (A) | 869.88 | 60.91 | 1405.85 | 86.70 |
| 512/2/128/64 (B) | 869.36 | 60.72 | 1399.76 | 86.75 |
| 512/1/128/128 (D) | 983.56 | 60.83 | 1412.55 | 86.17 |
| 512/2/128/gate (F) | **985.86** | 60.70 | **1415.40** | 86.55 |

Q8_0 `mul_mat_q<8,64,false>` dropped from 13.65 s to 9.38 s at J=128. Q8_0
J=128 uses 89 VGPR / 0 scratch. MUL_MAT 1186/1186 and MUL_MAT_ID 865/865 both
pass. Occupancy does not change allocation (A == B), so variants C and E were
skipped.

Next candidate steps if continuing: J=128 MXFP4 with a real MXFP4 model, and
the double-buffer Y kernel change from the handoff, each on the variant F base.
