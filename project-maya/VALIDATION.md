# gfx906 validation

Date: 2026-10-22. Source: Project Maya v1.1.21,
`451f9cb6a21ea65673bdde2e57b4a670ae2b8859`.
ROCm base: `mixa3607/rocm-gfx906:10.1-complete`, index digest
`sha256:b1d72163863a56b6b2bf498d159c1dc17627f8751aed6c8b8de2ebe9882972b4`.

## Build

- All 347 Ninja build steps succeeded, including `maya`, `maya-ds4`, GGML MMQ,
  CPU expert kernels and upstream test executables.
- Both engines' `ldd` checks passed in the build image.
- Runtime `--help` passed without a GPU. Both engines' source stamps match the
  packaged sources; the installer's build step reuses both binaries instead of
  attempting a runtime compilation.
- No GPU architecture spoofing or fast-math flags were needed. The upstream
  changes are kept in `build-context/patch/gfx906.patch`.
- Nine isolated build-script checks passed (existing/missing/denied manifests,
  force mode, push/load targets, failed-build propagation and invalid arguments).
- Bash syntax, Compose configuration, YAML parsing and Kubernetes server-side
  dry-run passed.

Published runtime:
`registry.arkprojects.space/apps/maya-gfx906:v1.1.21-rocm-10.1`
(`sha256:56060bf3f2408f13d94a7cb6aa5a3a327004016740304bb9d06036dabdc8ec73`).

Published test target:
`registry.arkprojects.space/apps/maya-gfx906:v1.1.21-rocm-10.1-test`
(`sha256:9cca85deb288dd970c18f824ad09d7e47315a8d4ab4b0188369a3f2e51d2e1c0`).

Both engine binaries, the Python server and their shared libraries also passed
GPU-free help/import checks in the final runtime image. The final source-stamp
and prebuilt-reuse checks passed in Job `maya-gfx906-runtime-nzq5h`, without GPU
mounts or privileged access.

## Environment findings

The existing `apps-ml` ROCm workloads use privileged containers. A first test
with just hostPath `/dev/kfd` and `/dev/dri` reproduced:

```text
/sys/class/kfd/kfd/topology/nodes/2/properties: Operation not permitted
Unable to open /dev/kfd read-write: Operation not permitted
hipGetDeviceProperties: no ROCm-capable device is detected
```

This is the container's device-cgroup policy, not an unsupported gfx906 engine.
The Job now uses the same privileged GPU access as the existing deployments.
The alternative is an AMD GPU device plugin that grants the devices. Docker's
`--device` already supplies that permission without privileged mode.

The 50 upstream Python HIP/architecture regression tests passed even in the
unprivileged test (these are mocked tests, **not** GPU performance measurements).
The fake 128 tokens/s benchmark lines printed by those tests are not MI50 results.

## Single-card GPU results

Node: `kube-worker6.arkprojects.lan`, Radeon Instinct MI50 32 GB,
`gfx906:sramecc+:xnack-`. HIP device 0, `HSA_XNACK=0`, no architecture override,
no `HSA_FORCE_FINE_GRAIN_PCIE`. Final patched Job: `maya-gfx906-test-lp5zc`.

- Actual installer `--backend hip --check --gpu 0`: passes, lists all four MI50s.
- Wave64 probe: passes all 128 threads (four logical warps), including different
  low/high-half ballots, shuffles and shared-memory synchronization.
- Selected CTest set: **22 passed, 3 skipped, 0 failed** (25 registered, 72.49 s).
  Passes include `hip_intrinsics`, both handoffs, expert staging, F32 GLM prompt
  attention, MMQ, GLM layer/model parity, exhaustive INT8 latent conversion,
  IQ1_S, EXL3, multi-row GEMV and mlock.
- Skips: `hip_glm_expert_helper` (only one visible device),
  `hip_prefill_hipblaslt_gemm`, `hip_prefill_fused_parity` (unavailable paths).
- Expert parity sweep: **620/620** comparisons pass with `max_abs=0`, `rel_L2=0`,
  `bit_identical=yes`.

The final patched image also passed on physical MI50 1 with
`HIP_VISIBLE_DEVICES=1` (logical device 0): Job `maya-gfx906-gpu1-fixed-qmfb4`,
**22 passed, 3 skipped, 0 failed**, 79.15 seconds, plus the wave64 probe,
50 Python tests and **620/620** bit-identical expert comparisons.

Before the final signed-zero fix, the original 24-test smoke set also passed on
physical MI50 0 (`maya-gfx906-test-25zh5`, 71.98 s) and MI50 1
(`maya-gfx906-final-r8wdb`, 76.26 s). These earlier runs did not include
`glm_lat8_test`; the final 25-test result above supersedes them.

Raw logs are retained locally in `project-maya/logs/` (ignored by Git); Jobs
expire after one hour. No pre-existing workload was stopped or reconfigured.

## Full-suite investigation

The first full run (`maya-gfx906-full-g9ft6`) registered 71 tests:
64 passed, 3 skipped, 4 failed, 206.85 seconds. Three failures require external
model fixtures, which are intentionally not downloaded by the test image:

- `ple_parity`: missing Qwen PLE GGUF shard.
- `expert_parity`, `pool_test`: missing `pack/full/experts.bin`.

The remaining failure, `glm_lat8_test`, exposed a real gfx906 parity issue.
Upstream `glm_lat8.cuh` clears the sign of a zero FP16 result on **all** HIP
targets to match the F32 reference observed on Radeon. On MI50, the F32
reference retains `-0` for code zero times a negative normal FP16 scale.
The blanket normalization produced 61,440 mismatched words. The port now
keeps the native FP16 product on gfx906 only; non-normal scales retain the
upstream F32 fallback. This test is included in the default regression set,
not skipped or relaxed.

The final patched image passes this exhaustive test: every INT8 code is paired
with every finite FP16 scale, checking both four-value and eight-value reads
against the GPU's F32 reference, including signed zero and subnormal scales.

The final full run (`maya-gfx906-full-fixed-c9j2d`) registered the same 71 tests:
**65 passed, 3 skipped, 3 failed**, 204.81 seconds. Only the three missing-fixture
failures listed above remain; CTest and the Job retain their failure status
(exit 8), rather than masking those failures. `glm_lat8_test` now passes both
inside CTest and as a separate executable:

```text
glm_lat8_test: 2031616 reads of 8 values (every code x every finite FP16 scale), 0 words differ - OK
```

## Full-model DeepSeek-V4.1 Q8 API smoke/bench

The worker's **host-local** `/srv/ml/shared-hf-cache` is different from the
`shared-hf-cache` PVC. It already contains all nine shards of
`unsloth/DeepSeek-V4.1-Flash-1017-GGUF`, revision
`60ad3651641b5c97679c807e064ab1d7a3ca1455`, `UD-Q8_K_XL` (508,376,763,197
bytes). Shard sizes match Maya's pinned manifest; this was not a full SHA256
scan. GGUF metadata reports `deepseek41`; the F32/BF16/MXFP4/MXFP8 tensor
formats are supported. The cached `UD-IQ1_M` is not interchangeable: it contains
GGML type 19, which this version's packer does not support.

Job `maya-ds41-q8-bench-fx5fk` successfully loaded the **full** Q8 model and
served real `/v1/chat/completions` requests, exiting 0. No weights were downloaded
or copied. The host cache was mounted read-only as `/hf`; the index pack and
results were written separately to
`/srv/ml/maya-gfx906-tests/maya-ds41-q8-bench-fx5fk-8xlpd/`.

Configuration: final runtime digest above, 4 x MI50, 40 layers split 10 per GPU,
`--tp 1 --threads off --prefill-chunk 0`, context 2048, 16 CPU threads,
4096 MiB reserved per GPU, `--mmap-experts on`. Job limits: 16 CPUs / 160 GiB
RAM. Vision, drafter, prompt/expert skipping and the explicit RAM tier were
disabled. This is a conservative compatibility baseline, **not** an optimized
chunked-prefill or tensor-parallel benchmark. Existing services were not stopped;
all four cards were idle and essentially empty before launch, but hostPath access
does not reserve them against other workloads.

- Pack: 47,284 indexed tensors; 16.4 GB BF16, 0.5 GB F32, 288.8 GB MXFP4 and
  202.8 GB MXFP8 (Engram). Pack creation does not copy the tensor data.
- API ready: **82.80 s** after benchmark start, including packing/loading.
- 5,432 routed experts placed in VRAM, 9,928 read through the CPU/file lane.
  Approximately 4 GiB remained free per card. Upstream DS4 logs label the HIP
  devices `CUDA0` through `CUDA3`; these runs actually used gfx906 HIP binaries.
- Arithmetic returned **`4`**; the capital-of-France question returned **`Paris`**.

| Request | Prompt / cached tokens | Output tokens | Prefill tok/s | Decode tok/s | API wall s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Warmup | 7 / 0 | 8 | 2.3 | 6.0 | 4.397 |
| Arithmetic | 18 / 0 | 2 | 8.1 | 15.8 | 2.351 |
| Geography | 18 / 0 | 2 | 11.0 | 13.0 | 1.789 |
| Summary | 206 / 0 | 9 | 19.8 | 8.5 | 11.452 |
| Same summary again | 206 / 205 | 9 | 8.5 | 10.4 | 0.987 |

Rates are the real engine's reported timings, not Python-test mock benchmarks.
The repeated summary was identical; its prefill rate counts **one new token**,
not all 206 tokens. Decode measurements on 2-9 tokens are noisy and are not a
sustained-throughput claim. The benchmark script is `bench/ds41-q8.py`.

A second successful Job, `maya-ds41-q8-long-6jxs6`, repeated those checks and
added two **128-output-token** requests. API ready time was **68.82 s**. The
same configuration was used; neither run flushed the host page cache, so these
are not controlled cold-storage measurements.

| Request (second run) | Prompt / cached tokens | Output tokens | Prefill tok/s | Decode tok/s | API wall s |
| --- | ---: | ---: | ---: | ---: | ---: |
| Summary | 206 / 0 | 9 | 26.4 | 9.5 | 8.766 |
| Same summary again | 206 / 205 | 9 | 9.5 | 10.4 | 0.973 |
| Count integers, limit 128 | 22 / 0 | 128 | 16.2 | **10.6** | 13.495 |
| Same count again | 22 / 21 | 128 | 13.7 | **14.8** | 8.755 |

Both counting replies were identical (`1, 2, 3, ... 43,`) and ended at the
requested token limit, not EOS. This is a short, repetitive decode workload,
not a representative long-form quality/throughput benchmark. The engine's
cumulative CPU-lane share decreased from 50.1% after the first count to 39.3%
after the repeat as expert caches warmed; the improvement is not solely from
reusing 21 prompt tokens. No draft tokens were generated. Arithmetic and
geography answers also remained correct in the second run.

Second-run artifacts are on the worker under
`/srv/ml/maya-gfx906-tests/maya-ds41-q8-long-6jxs6-hnkv2/`.
Both runs' JSON responses, timing summaries, metrics and engine/server logs
were also copied into the local, Git-ignored `project-maya/logs/` directory.
The benchmark shuts down its API/engine after the requests; no persistent
service or external endpoint was created.

### Context sweep: 0 / 2048 / 8192 + TG 256

Job `maya-ds41-ctx-tg256-gl8ck` completed successfully. Script:
`bench/ds41-context.py`. Same runtime, 4 x MI50 layer split, 16 CPU threads,
160 GiB Job limit, mmap/file experts and conservative 16-token prefill windows
as above; fixed **8704-token capacity** for all three cases (engine reports
`kv=fp4`). Each case starts a new engine: **zero KV-prefix reuse** was verified
in every `DONE` response. The host page cache was not flushed. Each run is one
measurement, not a repeated statistical benchmark.

The two nonempty prompts are synthetic experimental records rendered with the
model's chat template, truncated in the middle to exactly the specified token
count while preserving the generation header. `ctx=0` means no user prompt:
**one BOS token** is fed because the engine needs an initial token. Greedy
generation uses `--eos -1` to force **exactly 256 output tokens**, even beyond
an EOS. This is a throughput test rather than normal chat/answer-quality testing.
No drafter, vision or expert/prompt skipping was enabled.

| Requested ctx | Actual input tokens | Output tokens | Prefill tok/s | Prefill s | Decode tok/s | Decode s | Request wall s |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 1 (BOS) | 256 | n/a | 0.142 | **8.57** | 29.873 | 30.015 |
| 2048 | 2048 | 256 | **23.93** | 85.577 | **8.96** | 28.581 | 114.159 |
| 8192 | 8192 | 256 | **24.74** | 331.094 | **8.36** | 30.610 | 361.708 |

Engine startup, excluded from request timings: 59.56 / 65.92 / 55.55 s.
Decode rate uses the native serve protocol's output count (256) divided by its
decode time, consistent with the preceding API measurements. There are 255
subsequent forward steps after sampling the first output from prefill logits;
using that numerator instead gives 8.54 / 8.92 / 8.33 steps/s. The BOS-only
prefill rate is deliberately not compared with real prompt prefill.

The 8K prompt completed without errors. Its output began with a relevant
summary of the experimental procedure; generation was deliberately continued
to the requested length. All three cases' inputs, output IDs/text, commands,
protocol and engine logs, and timing summary are stored on the worker at
`/srv/ml/maya-gfx906-tests/maya-ds41-ctx-tg256-gl8ck-fx5sq/` and copied into
the local ignored `project-maya/logs/` directory. The Job reached `Complete`,
and all four GPUs returned to idle with approximately 10.46 MiB used each.

### Russian persistent-engine tuning

Job `maya-ds41-ru-tune-p6zn5` completed with exit 0. The user's starting point
was 48-56 CPU threads, chunk 2048 and near-full VRAM utilization. The suite
(`bench/ds41-tune.py`) runs Russian prompts on climate adaptation, database
reliability, historical research and ecology. Each configuration has one engine
process: a 2048-token ecology warmup/TG 64, then climate 2048, databases 2048,
history 8192 and ecology 2048, all **TG 256**, followed by arithmetic/geography
checks. No process restart occurs between topics. Prefix KV reuse was **zero**
for every request; expert caches and the learned profile remain live.

All configurations used the same input IDs/order and a separate copy of the
same upstream generic expert profile. The setup retained TP 1, enabled host
threads/chunked prefill, reserved 512 MiB per GPU, used mmap experts and a fixed
8704-token capacity, and disabled speculation, vision and expert/prompt
skipping. No CPU quota was imposed (`cpu.max=max 100000`, no throttling).
A cgroup cap of **192,000,000,000 bytes** (178.8 GiB) constrained RAM including
charged file cache; peak observed usage was 191.995 GB. The cgroup reached its
limit/reclaimed pages (`memory.events:max=9`) but had **no OOM/OOM kills**.

| CPU threads | Chunk | 2K prefill tok/s, aggregate | 8K prefill tok/s | TG tok/s, aggregate | Four measured requests, wall s |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 48 | 2048 | 86.42 | 169.85 | 12.20 | 203.28 |
| **56** | **2048** | **87.91** | **183.33** | **12.29** | **197.89** |
| 56 | 8192 | 83.60 | 116.71 | 12.24 | 227.32 |

Aggregates divide total tokens by total engine time (not an arithmetic mean of
rates). Warmup, startup and the two tiny checks are excluded. For 56/chunk 2048:

| Topic | Prompt tokens | Prefill tok/s | Decode tok/s | Request wall s |
| --- | ---: | ---: | ---: | ---: |
| Climate | 2048 | 85.63 | 11.92 | 45.39 |
| Databases | 2048 | 87.26 | 11.86 | 45.05 |
| History | 8192 | 183.33 | 12.18 | 65.70 |
| Ecology | 2048 | 91.01 | 13.30 | 41.75 |

Chunk 2048 beats 8192 here; 56 versus 48 CPU threads is only a modest difference,
not a statistically established optimum. This is a sequential single-pass
sweep: host file cache carries over across configurations, and generated text
differs, so the runs do not isolate the effect of each knob. The corpus is
synthetic Russian text with rotating facts, not a representative quality suite.
The earlier English/windowed runs are a different corpus/coldness/configuration
and cannot establish an exact speedup factor for these settings.

Basic checks returned `4` and `Москва` in all three configurations. Long replies
were relevant Russian text, but the 256-token outputs were **not bit-identical**
across configurations. There was no new weight quantization or omitted expert;
this is not proof of equivalent perplexity or full-model numerical parity.
EOS was disabled only to force benchmark length; post-EOS text is ignored by the
basic checks and is not a normal user-facing answer.

The log contains hipBLASLt `gfx906` library/kernel lookup warnings. The DS4
source falls back to hipBLAS when no Lt solution runs; the measured suite still
completed. These warnings are not being counted as successful Lt acceleration.
Also, the **512 MiB CLI reserve is not the final free VRAM**: later workspaces
reduced sampled free VRAM to 135-149 MiB at peak. A larger reserve may be needed
for deployment headroom even though these runs did not exhaust VRAM.

Artifacts: worker
`/srv/ml/maya-gfx906-tests/maya-ds41-ru-tune-p6zn5-dg89d/`, also copied to local
ignored `project-maya/logs/`. The initial per-variant sampler accidentally read
the host cgroup root; use **`cgroup-resources.jsonl`** for this Job's CPU/memory
statistics. The supplementary `kubectl exec` sampler exited 137 when Kubernetes
tore down the successful pod; that is **not** the benchmark's exit status.
The sampler now resolves its own cgroup path in subsequent runs.

#### Follow-up: tensor parallelism and explicit RAM copies

Job `maya-ds41-ru-followup-5cctk` also completed with exit 0, reusing the exact
same Russian corpus/order. All candidates used 56 CPU threads, chunk 2048 and
reserve 512. The final candidate repeated the preceding TP 1/mmap configuration
as a control, rather than relying only on its earlier timings.

| Configuration | 2K PP tok/s | 8K PP tok/s | Aggregate TG tok/s | Measured request wall s | Engine load s |
| --- | ---: | ---: | ---: | ---: | ---: |
| TP 2, mmap | 83.87 | 121.38 | **16.56** | 202.60 | 71.90 |
| TP 1, `--mmap-experts off` | 85.48 | **182.97** | **14.95** | **185.14** | 190.70 |
| TP 1, mmap, control repeat | 85.99 | 173.56 | 12.20 | 202.61 | 87.84 |

TP 2 here means two groups of two MI50s, each group holding 20 layers; the
individual experts' FFNs are split between the pair's devices. It improves
decode but sacrifices long-prompt prefill on this suite. With TP 1/RAM copies,
all **9343 CPU-lane experts** were copied into anonymous RAM (**175.7 GB**, two
NUMA parts, 132.8 s copying). This is distinct from the experimental dynamic
`STRATA_DS4_RAM_TIER`, which remained disabled. The engine's measured CPU-lane
expert time decreased from roughly 0.134 ms in the mmap control to 0.049 ms
with copies; copying changes memory placement/NUMA execution, not the weights.
During measured TG, disk reads fell to roughly 0.14-0.17 MB/token rather than
about 19-41 MB/token in the mmap control.

The RAM-copy candidate improved aggregate TG about **22.5%** over the control;
TP 2/mmap improved TG about **35.7%**, but its four-request total time was
essentially unchanged because prefill slowed down. The control TG (12.20)
agreed closely with the earlier 12.29, while its 8K PP varied 183.33 -> 173.56.
These are useful workload-specific observations, not confidence intervals.

All three configurations passed both basic checks and produced relevant
Russian answers. Every measured request had zero cached prompt tokens and 256
generated tokens; speculative decode stayed off. No OOM occurred. RAM-copy
and the control reached the 192 GB cgroup cap/reclaimed pages; TP 2/mmap's
maximum sampled charge was 126.60 GB. Shared file-cache ownership means these
charges are not the total physical footprint of every mapped model page.

Artifacts: `/srv/ml/maya-gfx906-tests/maya-ds41-ru-followup-5cctk-rfmmn/`,
also copied under local ignored `project-maya/logs/`. This Job's per-variant
`resources.jsonl` resolves the correct container cgroup; memory peak/event
counters are cumulative within the Job, even as engines are restarted between
configurations.

#### Final comparison with deployment VRAM headroom

Job `maya-ds41-ru-final-7cmdv` completed with exit 0. Both candidates used
56 CPU threads, chunk 2048, `--mmap-experts off` and **reserve 896 MiB**, with
the same persistent-engine Russian suite and 192 GB cap. Reserve was increased
to accommodate workspaces allocated after the engine's initial placement report.

| Configuration | 2K PP tok/s | 8K PP tok/s | Aggregate TG tok/s | Measured request wall s | Engine load s |
| --- | ---: | ---: | ---: | ---: | ---: |
| **TP 2, RAM copies, reserve 896** | **102.08** | 130.39 | **16.93** | **183.50** | 167.37 |
| TP 1, RAM copies, reserve 896 | 84.89 | **161.21** | 14.88 | 192.02 | 156.38 |

The TP 2 candidate copied all **9520** CPU-lane experts into RAM (**179.0 GB**,
two NUMA parts). Sampled cgroup charge peaked at **190.08 GB**, without a
memory-limit event or OOM. Minimum sampled free VRAM was **644-671 MiB/card**.
TP 1 copied all **9429** remaining experts (**177.3 GB**, two NUMA parts),
peaked at **192.00 GB** with cache reclamation but no OOM, and kept at least
**524-536 MiB/card** free in the samples. Memory samples are taken every two
seconds and are not a guarantee against shorter-lived allocation peaks.

| Topic | TP 2 PP / TG tok/s | TP 2 wall s | TP 1 PP / TG tok/s | TP 1 wall s |
| --- | ---: | ---: | ---: | ---: |
| Climate, 2048 + 256 | 102.63 / 17.57 | 34.53 | 83.72 / 14.66 | 41.93 |
| Databases, 2048 + 256 | 101.83 / 16.55 | 35.59 | 82.40 / 15.15 | 41.75 |
| History, 8192 + 256 | 130.39 / 16.68 | 78.18 | 161.21 / 14.65 | 68.29 |
| Ecology, 2048 + 256 | 101.80 / 16.97 | 35.21 | 88.82 / 15.07 | 40.05 |

For this mix, **TP 2 + RAM copies** is the fastest candidate with tested VRAM
headroom. **TP 1 + RAM copies** remains preferable for the measured 8K-prompt
case: it finishes that entire request about 10 s sooner despite slower TG.
The TP 2 candidate's TG is about 39% above the 12.20 tok/s mmap control;
its 2K prefill is about 19% higher, but 8K prefill is lower. This is not a
universal ranking, nor an exact factor over the original English cold-process
benchmark. The suite remains synthetic, single-pass, with shared host cache.

Both configurations passed the two basic answer checks, kept zero KV-prefix
reuse, and generated exactly 256 tokens for each measured topic. Speculation
and expert/prompt skipping stayed off; weights/formats were unchanged. Text
differs across execution paths, and no perplexity or formal numerical-parity
test was performed, so no claim of bit-identical outputs or proven equal
quality is made.

Reproduce the selected configuration with:

```bash
python3 project-maya/bench/run-tune-k8s.py --configs \
  '[{"cpu":56,"chunk":2048,"reserve":896,"tp":2,"mmap":"off","label":"ram-copy"}]'
```

For normal serving, use the same engine options but **omit `--eos -1`** (that
flag is only to force TG length in the benchmark). Keep the expert profile in
a writable output directory, never in the read-only HF snapshot. All weights
were reused locally and no permanent server was created.

Final artifacts: worker
`/srv/ml/maya-gfx906-tests/maya-ds41-ru-final-7cmdv-9jd28/`, also copied into
local ignored `project-maya/logs/`. All three tuning Jobs reached `Complete`.
After the final Job, all four GPUs were idle at approximately 10.46 MiB used
each, and the existing llama-server/comfyui workloads remained running without
new restarts.

## Max-ILP compiler experiment

The original published build has `CMAKE_HIP_FLAGS:STRING=` (empty), Release
`-O3 -DNDEBUG`, architecture `gfx906`. Job `maya-flags-baseline-xdqgq` checked
its test image. The experimental build adds only
`-mllvm -amdgpu-sched-strategy=max-ilp` to the HIP compiler flags; no fast-math,
new quantization, speculative decode or expert/prompt skipping was enabled.
Source, local patch and ROCm base are unchanged. The runtime images share their
first six layers; their standard tags were not overwritten.

Published under `registry.arkprojects.space/apps/maya-gfx906`:

| Variant | Tag | Image index digest |
| --- | --- | --- |
| Baseline | `v1.1.21-rocm-10.1` | `sha256:56060bf3f2408f13d94a7cb6aa5a3a327004016740304bb9d06036dabdc8ec73` |
| Max-ILP runtime | `v1.1.21-rocm-10.1-max-ilp` | `sha256:40d1272d4f384a7eb5fa8f113a3d468add4e91e40b354fea1847e31fe9abf80c` |
| Max-ILP tests | `v1.1.21-rocm-10.1-max-ilp-test` | `sha256:311759f9e43016715515d7c4195c7f31a62a39609c1ba7a8d4f980f1f73496a4` |

Job `maya-max-ilp-smoke-6pkhb` verified the flag in `CMakeCache.txt`, the build
stamp and **all 102 HIP compilation entries** in `compile_commands.json`,
including DS4 units. Link-step warnings about unused `-mllvm` do not describe
these compilation steps. Source SHA remains
`451f9cb6a21ea65673bdde2e57b4a670ae2b8859`, stamp `src=e451598f9c8d2d89`.
The test image's `maya-ds4` SHA256 is
`3e1f31dc32d6ccd2a3562033b93f5ef54751bdfc435881db5caa414a8b7cb7d9`.
The Job completed successfully: 50 Python tests passed, wave64 probe passed,
CTest **22 passed / 3 skipped / 0 failed**, expert sweep **620/620 bit-identical**
within the new build. This is not a baseline-vs-max-ILP full-model parity test.

### Persistent-engine A/B benchmark

Baseline Job `maya-ds41-ilp-base-8jf8v` and max-ILP Job
`maya-ds41-max-ilp-n4b46` completed successfully. Each loads one engine, performs
one ecology warmup (2048 + 64), then **three** passes over the same four Russian
topics without restarting. Tokenized inputs were compared and are identical.
Configuration: four MI50s, TP 2, 56 CPU threads, chunk 2048, RAM expert copies,
reserve 896 MiB, context capacity 8704, greedy TG 256. No CPU quota; total cgroup
memory limit 192 GB decimal. Each measured request has zero cached prompt tokens.
The generic initial expert profile is copied separately for each run; its updates
and expert caches persist within that run. The host page cache is not flushed.

| Build / pass | 2K PP tok/s | 8K PP tok/s | Aggregate TG tok/s | Four-request wall s |
| --- | ---: | ---: | ---: | ---: |
| Baseline / 1 | 98.69 | 138.07 | 18.74 | 176.24 |
| Max-ILP / 1 | 94.31 | 133.75 | 19.53 | 178.82 |
| Baseline / 2 | 97.29 | 136.41 | 20.23 | 173.82 |
| Max-ILP / 2 | 96.32 | 136.09 | 22.16 | 170.19 |
| Baseline / 3 | 97.50 | 138.56 | 20.23 | 172.77 |
| Max-ILP / 3 | 95.00 | 129.89 | 22.60 | 173.07 |
| **Baseline / pooled 2-3** | **97.40** | **137.48** | **20.23** | **173.30** |
| **Max-ILP / pooled 2-3** | **95.65** | **132.92** | **22.38** | **171.63** |

Rates use summed token counts divided by summed engine times, not arithmetic
means of rates. Pooled wall time is the mean time per four-request pass.
In passes 2-3, max-ILP improves TG **10.6%** (individual passes +9.5%, +11.7%).
PP is **1.8% lower at 2K** and **3.3% lower at 8K** in the pooled measurements;
the whole PP-heavy suite is only **1.0% faster**. The first pass improves TG
4.2% but takes 1.5% longer overall. These are workload observations, not
confidence intervals or proof that every kernel improved. The older single-pass
16.93 tok/s result is not the correct denominator: even the baseline reaches
20.23 tok/s as its expert caches warm up.

Both runs passed `4` / `Москва` checks. Both reached the 192 GB cgroup cap with
cache reclamation (`memory.events:max` > 0), but no OOM/kill. Maximum sampled
VRAM use was 32108.1-32108.4 MiB on the fullest cards, essentially unchanged
between builds. Sampling every two seconds can miss shorter allocation peaks.
The synthetic greedy outputs can differ across builds and repeated requests;
full-model bitwise parity and quality/perplexity remain untested. The retained
hipBLASLt gfx906-library limitation is not fixed by a scheduler flag.

Artifacts are copied into ignored `project-maya/logs/` from worker directories
`/srv/ml/maya-gfx906-tests/maya-ds41-ilp-base-8jf8v-fngrp/` and
`/srv/ml/maya-gfx906-tests/maya-ds41-max-ilp-n4b46-zp242/`. Compile proof and
smoke results are in `project-maya/logs/maya-max-ilp-smoke-6pkhb.log`.

### A/B/A control repeat

The subsequent baseline repeat, Job `maya-ds41-ilp-control-twvtm`, also completed
with exit 0, identical tokenized inputs, three passes and both basic checks
passing. It reused the original baseline digest and all the same engine settings.

| Baseline control pass | 2K PP tok/s | 8K PP tok/s | Aggregate TG tok/s | Four-request wall s |
| --- | ---: | ---: | ---: | ---: |
| 1 | 98.68 | 140.12 | 18.55 | 175.94 |
| 2 | 99.36 | 136.89 | 20.10 | 172.63 |
| 3 | 100.63 | 138.60 | 20.17 | 170.95 |
| **Pooled 2-3** | **99.99** | **137.74** | **20.13** | **171.79** |

Warm TG returned to **20.13 tok/s**, only **0.48% below** the first baseline.
Max-ILP's 22.38 tok/s is **11.2% higher** than this repeat, supporting the
observed **roughly 11% decode gain** rather than an improvement caused solely
by run order. This is still a small sequential A/B/A experiment, not an
isolated randomized performance study. Relative to this control, max-ILP's
2K/8K PP is **4.3% / 3.5% lower**, and total suite wall time is essentially
unchanged (**171.63 vs 171.79 s**, 0.1% faster). Thus the decode gain is useful
for generation-heavy requests; no meaningful whole-suite speedup is established.

The control again reached the 192 GB cgroup cap with reclamation and no OOM,
with maximum sampled VRAM use 32108.1 MiB. Artifacts were copied from
`/srv/ml/maya-gfx906-tests/maya-ds41-ilp-control-twvtm-pd4hv/` into ignored local
logs. After completion all four cards were idle at 10.46 MiB used each;
existing llama-server/comfyui workloads were running with zero restarts.
Default flags/image remain unchanged; max-ILP stays an opt-in tagged image.

Reproduce the experimental run with:

```bash
python3 project-maya/bench/run-tune-k8s.py --rounds 3 \
  --prefix maya-ds41-max-ilp- \
  --image registry.arkprojects.space/apps/maya-gfx906:v1.1.21-rocm-10.1-max-ilp@sha256:40d1272d4f384a7eb5fa8f113a3d468add4e91e40b354fea1847e31fe9abf80c \
  --configs '[{"cpu":56,"chunk":2048,"reserve":896,"tp":2,"mmap":"off","label":"max-ilp"}]'
```

## v1.1.22 prefill experiment

Runtime `registry.arkprojects.space/apps/maya-gfx906:v1.1.22-rocm-10.1-max-ilp`
was built and published at index digest
`sha256:5f24929a1a8a5184500a9d764e024581c086e01e0bfdab4ebe83d46b2e746afb`.
Source is pinned to `ffe2e5e53fd5254e7f3492a20e8ad2b51b26a197`;
the existing gfx906 patch applies unchanged. HIP flags remain
`-mllvm -amdgpu-sched-strategy=max-ilp`. Standard image tags/defaults are not
changed. No custom kernel rewrite, hipBLASLt gfx906 acceleration, new weights,
speculation or prompt/expert skipping is part of this experiment. TP 1 is
explicitly deferred.

Protocol: a fresh three-pass v1.1.21 max-ILP control, then GPU smoke and the
upstream attention-layout parity/microbenchmark, then v1.1.22 with
`DS4_HIP_ATTN_SWIZZLE=0` and `=1`, three passes per persistent engine. Retain
TP 2, 56 CPU threads, chunk 2048, reserve 896 MiB and RAM expert copies. A
separate one-pass diagnostic run enables `DS4_PROF=1` and
`DS4_PREFILL_STATS=1` with swizzle off. Diagnostic timings are not pooled into
the performance comparison. The profiler sums stage times across devices;
these are not independent wall-time contributions. The new expert-byte counter
is engine accounting, not a measurement of physical PCIe or storage traffic.

The layout benchmark reuses compiled DS4 objects plus the host-allreduce
object when linking: the upstream excluded test target omits the latter.
Neither engine nor upstream source is modified for that test. One-off launch,
verification and analysis scripts/specifications live in ignored
`project-maya/logs/v122-*.py`; final digests/job identifiers and copied artifacts
are recorded in `project-maya/logs/v122-experiment.json`.

### Verification and performance results

All Jobs completed successfully: control `maya-ds41-v122-control-rhh5w`, smoke
`maya-v122-smoke-h68mp`, A/B `maya-ds41-v122-ab-c5w2j`, and diagnostic
`maya-ds41-v122-prof-vtk6m`. The test image index digest is
`sha256:607c2c80b37d82de9f42f00cc3cb57c522a881af6bd318d2edd308ed34270394`
(`v1.1.22-rocm-10.1-max-ilp-test`, same registry). Compile proof verified the
flag in **104 HIP compilation entries**, architecture gfx906, stamp
`src=27cfaa42a9568ffe`. The test image's `maya-ds4` SHA256 is
`e27a3918b284605b58a614fb2cb3933de0b8fd60f1004853c72ce18a849a2d1d`.

Results: **51 Python tests passed**, wave64 probe passed, smoke CTest
**22 passed / 3 skipped / 0 failed**, expert sweep **620/620 bit-identical**,
and the new `ds4_prefill_stats_test` passed. The upstream layout benchmark
passed **64/64 bit-identical comparisons**, with finite outputs and intact
guards, across eight input cases, four grouping options and swizzle off/on.
This does not establish full-model bitwise parity or equal perplexity.

The layout microbenchmark does show a local kernel improvement: with group 8,
median GPU time for `steady512` fell **11.824 -> 8.615 ms** (27.1% less time),
and `early512` **2.207 -> 1.598 ms** (27.6% less). These synthetic kernel times
must not be reported as an equivalent full-prefill improvement.

| Build / pass | 2K PP tok/s | 8K PP tok/s | Aggregate TG tok/s | Four-request wall s |
| --- | ---: | ---: | ---: | ---: |
| v1.1.21 max-ILP / 1 | 88.48 | 135.14 | 19.79 | 181.80 |
| v1.1.21 max-ILP / 2 | 91.94 | 132.27 | 22.31 | 174.67 |
| v1.1.21 max-ILP / 3 | 95.32 | 136.00 | 22.47 | 170.28 |
| v1.1.22 swizzle off / 1 | 91.86 | 135.58 | 21.01 | 176.05 |
| v1.1.22 swizzle off / 2 | 91.02 | 133.00 | 22.40 | 174.83 |
| v1.1.22 swizzle off / 3 | 92.16 | 132.44 | 22.54 | 173.97 |
| v1.1.22 swizzle on / 1 | 90.32 | 136.04 | 20.92 | 177.19 |
| v1.1.22 swizzle on / 2 | 92.71 | 134.26 | 22.46 | 172.90 |
| v1.1.22 swizzle on / 3 | 94.12 | 136.74 | 22.47 | 170.77 |
| **v1.1.21 / pooled 2-3** | **93.60** | **134.11** | **22.39** | **172.48** |
| **v1.1.22 off / pooled 2-3** | **91.58** | **132.72** | **22.47** | **174.40** |
| **v1.1.22 on / pooled 2-3** | **93.41** | **135.49** | **22.46** | **171.83** |

Pooled rates are total tokens / total engine time; wall is the mean per pass.
Against v1.1.21, the new release without swizzle has **2.2% / 1.0% lower PP**
at 2K/8K and essentially the same TG (+0.35%). Swizzle improves PP about
**2.0% / 2.1% over v1.1.22 off**, leaving TG unchanged; wall improves 1.5%.
Against v1.1.21, v1.1.22 with swizzle is **-0.2% / +1.0% PP**, +0.33% TG,
and only **0.37% faster overall**. This small sequential test establishes no
meaningful release-level speedup for our TP 2 configuration; the swizzle result
is a promising small local improvement, not a demonstrated large system gain.
No TP 8 headline factor is extrapolated to two-member groups.

Input token IDs matched across all runs; every measured request had zero KV
reuse and exactly TG 256. Both basic checks passed in every engine. All runs
reached the 192 GB cap with reclamation but **zero OOM/kills**. Maximum sampled
VRAM use was 32108.5 MiB in the control and 32171.9 MiB across v1.1.22 runs.
Memory event/peak counters are cumulative across the off/on variants sharing
one Job. Existing services had no new restarts; all four cards were idle after
completion at 10.46 MiB used each.

### What the profile actually tells us

The separate swizzle-off diagnostic excludes its warmup and checks below.
Times are **sums over GPU event intervals on all four devices**, not request
wall time and not independently additive bottleneck measurements.

| Prompt | Attention ms | Routing/shared ms | Experts including streaming waits ms | Sparse attention alone ms |
| --- | ---: | ---: | ---: | ---: |
| Climate 2K | 10063 | 1127 | 32274 | 3089 |
| Databases 2K | 9849 | 1129 | 33159 | 3089 |
| History 8K | 42805 | 4667 | 159810 | 14028 |
| Ecology 2K | 10034 | 1127 | 34117 | 3090 |

The expert stage accounts for **74-77%** of these summed intervals; sparse
attention alone is about **7%**. A 25-28% improvement to the latter is therefore
consistent with only a small overall improvement. The expert stage includes
compute, streaming waits and associated synchronization: this profile alone
does **not** prove that physical PCIe bandwidth is the sole bottleneck.

The new payload counters are particularly useful here: approximately
**44.7-44.8 GB per GPU per 2048-token chunk**, **179.0 GB summed across cards**,
and **715.9 GB** across cards for the four-chunk 8K prompt. The TP 2 batch path
streams its host-expert batches repeatedly; the source increments this counter
after each `stream_expert` call in `copy_ahead`. Our host experts are copied
into RAM, so these numbers do **not** mean that much SSD traffic. They exclude
other transfers and cannot be used as a hardware PCIe bandwidth measurement.

This points the next non-invasive experiment toward **chunk 4096** and, if
needed, the existing `DS4_RING_MB` streaming-buffer setting, rather than CPU
thread count or more attention-specific work. Larger chunks could amortize
repeated payloads but require more workspace and may reduce pipeline overlap;
the earlier TP 1/mmap chunk-8192 test lost badly, so no gain is assumed. Neither
these follow-ups nor deferred TP 1 are part of the completed v1.1.22 test.

Artifacts: worker `/srv/ml/maya-gfx906-tests/` directories
`maya-ds41-v122-control-rhh5w-5qznt`, `maya-ds41-v122-ab-c5w2j-666kc`, and
`maya-ds41-v122-prof-vtk6m-qkv7x`, copied under ignored local logs. Default
source/version/image and swizzle setting remain unchanged.

## Chunk / streaming-ring follow-up

This experiment keeps the pinned v1.1.22 max-ILP runtime, swizzle on, TP 2,
56 CPU threads, RAM expert copies, reserve 896 MiB, context 8704 and the same
192 GB cap without CPU quota. A fresh chunk-2048/ring-400 control is compared
with chunk 4096/ring 400, three passes per persistent engine on identical inputs.
No profiler is enabled in these performance runs. TP 1 remains deferred.

Ring-size follow-ups retained the target of approximately 512 MiB free per card. The
sysfs VRAM total on these cards is **32752 MiB**, not a rounded 32768 MiB; free
headroom is computed from the actual total minus sampled usage. Memory samples
cannot rule out shorter-lived peaks. Defaults and existing services are unchanged.

### Chunk 2048 vs 4096

Job `maya-ds41-chunk4k-456rc` completed successfully with both basic checks
passing for both configurations. Input token IDs match the earlier corpus;
every measured request has zero cached tokens and TG 256. Both use
`DS4_HIP_ATTN_SWIZZLE=1`, `DS4_RING_MB=400` and otherwise identical settings.

| Chunk / pass | 2K PP tok/s | 8K PP tok/s | Aggregate TG tok/s | Four-request wall s |
| --- | ---: | ---: | ---: | ---: |
| 2048 / 1 | 87.73 | 129.43 | 20.57 | 183.12 |
| 2048 / 2 | 96.14 | 129.32 | 22.31 | 173.17 |
| 2048 / 3 | 92.46 | 134.19 | 22.52 | 172.97 |
| 4096 / 1 | 89.78 | 165.93 | 20.02 | 168.97 |
| 4096 / 2 | 90.36 | 171.18 | 21.89 | 162.64 |
| 4096 / 3 | 92.85 | 172.14 | 22.36 | 159.57 |
| **2048 / pooled 2-3** | **94.26** | **131.71** | **22.41** | **173.07** |
| **4096 / pooled 2-3** | **91.59** | **171.66** | **22.12** | **161.10** |

Chunk 4096 improves 8K PP **30.3%**, with the whole 8K + TG256 request taking
**59.50 s instead of 73.76 s** over passes 2-3. The four-topic suite takes
**6.9% less wall time** and **9.9% less prompt time**. The tradeoff is **2.8%
lower 2K PP** and **1.3% lower TG**. These are sequential workload measurements,
not confidence intervals or a universal optimum.

Larger prefill buffers reduce expert residency: the engine copies **9611**
host experts (**180.7 GB**) versus **9520** (**179.0 GB**) with chunk 2048.
Minimum sampled free VRAM was **573-620 MiB/card** for chunk 4096 and
**583-620 MiB/card** for the control. Both reached the 192 GB cgroup cap with
reclamation and no OOM/kills. Peak/event counters remain cumulative within
this Job; the collector reports event deltas per variant.

Artifacts: worker directory
`/srv/ml/maya-gfx906-tests/maya-ds41-chunk4k-456rc-xw87f/`, copied into ignored
local logs, with summary `project-maya/logs/maya-ds41-chunk4k-456rc-comparison.json`.
The ring follow-up tested chunk 4096 with ring 200, 300, then a fresh
400 MiB control, three passes each. Source inspection confirms chunk/ring
buffers are allocated **before** expert placement, so changing ring size can
change resident expert count as well as streaming batches; its effect cannot
be reduced to nominal buffer bytes subtracted from final free VRAM.

### Ring 200 / 300 / 400 MiB

Job `maya-ds41-ring-hscp4` completed successfully. Each engine ran the same
warmup, 12 measured requests (three passes), then the two basic checks. All
checks passed, input token IDs matched, KV reuse was zero, and measured TG was
256. The table uses pooled passes 2-3, with total tokens / total engine time
and mean wall time per four-request pass; startup and warmup are excluded.

| Ring MiB | 2K PP tok/s | 8K PP tok/s | TG tok/s | Four-request wall s | Minimum sampled free VRAM MiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 200 | 87.26 | 165.59 | 22.33 | 165.76 | 591 |
| 300 | 93.62 | 168.31 | 22.29 | 160.26 | 577 |
| **400** | **93.32** | **170.42** | **22.28** | **159.89** | **573** |

Ring 200 takes **3.67% more wall time** than 400, with **6.49% lower 2K PP**
and **2.83% lower 8K PP**. Ring 300 and 400 are effectively tied overall
(300 takes 0.23% more time); 300 has 0.33% higher 2K PP, 1.24% lower 8K PP,
and essentially identical TG. This sequential sweep does not establish a
statistically significant winner between 300 and 400. Retain **400 MiB** as
the tested candidate: reducing it has no demonstrated benefit and does not
materially increase final VRAM headroom because expert placement consumes
most of the released space.

The RAM expert counts confirm that tradeoff: **9563 / 9587 / 9611** host
experts (**179.8 / 180.2 / 180.7 GB**) for ring 200 / 300 / 400. All variants
reached the 192 GB cap with reclamation, **zero OOM/kills**, and no CPU quota.
The ring-400 repeat is close to the previous chunk-4096 run: 8K PP -0.72%,
TG +0.70%, suite time -0.76%. Thus the substantial chunk-4096 prefill gain
survives another engine load; ring tuning adds no material speedup.

Recommended experimental candidate for this mixed 2K/8K workload: pinned
**v1.1.22 max-ILP, TP 2, chunk 4096, ring 400, swizzle on, 56 CPU threads,
RAM expert copies, reserve 896 MiB**. The chunk-2048 candidate remains an
option for short-prompt/decode-heavy work. No global defaults, weights or
quality-related options were changed; TP 1 remains deferred. Basic checks do
not establish full-model numerical equivalence or perplexity parity.

Artifacts: `/srv/ml/maya-gfx906-tests/maya-ds41-ring-hscp4-45mvz/`, copied
under ignored local logs; summary
`project-maya/logs/maya-ds41-ring-hscp4-comparison.json`. On completion all
four cards were idle at 10.46 MiB used each; existing llama-server/comfyui
pods had no new restarts. No further experiments are running.

## PR297 transfer-pruning experiment

The upstream PR297 change (`ce9a6976eaa9f7d156dac2121b4263da734ac582`)
was adapted onto pinned v1.1.22, retaining gfx906 fixes and max-ILP. Conflict
resolutions preserve both prefill statistics and the new pruning counters,
headers and tests. Opt-in patch SHA256:
`d6213985611b837c6e17332f6b4382c99dece4c4c792e44cda869a07091b8ac5`.
The patch skips transfers of experts not selected by routing, not expert
computation. Defaults remain unchanged.

- Runtime `v1.1.22-rocm-10.1-max-ilp-pr297`:
  `sha256:3c9d57ac9825be4faac437c05b0900262c44b24329fcb9ed41ca26d92aa7b009`.
- Test `v1.1.22-rocm-10.1-max-ilp-pr297-test`:
  `sha256:5274d633e0dea97bbd95f4bbe8e979f09decf5067bbfee3c893ecfb5bc6332fd`.

### Numerical checks

Job `maya-pr297-verify-wrv7v` completed with exit 0. Compile provenance
confirmed gfx906/max-ILP in all 104 HIP units, the selected patch hash and
stamp `src=0c3bc201b4ed2657`. DS4 binary SHA256:
`d4ad07d4075577688ea17974bb88149b22e68944dc896a72ef1574dc063588b0`.
The 51 Python tests, wave64 probe, selected CTest suite (22 pass / 3 skip),
620 expert parity comparisons, prefill-stats and new RAM-slice tests passed.
The RAM-slice test also passed a separate CPU ASan/UBSan run for TP 1/2/4,
NUMA 1/2 and guard/bounds checks.

The full cached model ran on TP2 with two NUMA RAM parts. Original v1.1.22
was run twice; then PR297 off and on. Each used the same initial profile,
disabled expert-cache swapping, chunk4096/ring400/swizzle and identical
512/2048/8192-token inputs. For each input, **64 x 129280 logits** (prompt-last
plus 63 decode positions) were finite and **bit-identical in all four runs**:
max absolute error and KL were zero, all 64 generated IDs matched. Both basic
checks passed in every run. Pruning was exercised: diagnostic logs reported
1758-3317 unpicked expert transfers skipped per GPU/request, not zero.
These bounded checks are not a general quality/perplexity guarantee.

### Throughput A/B/A

Job `maya-pr297-aba-9kh4h` completed with exit 0: off, on, off-repeat,
three measured passes per persistent engine. This restores normal expert-cache
updates, has no logit dumps or profiling, and retains the previous TP2/56-thread/
chunk4096/ring400/reserve896/swizzle/RAM-copy configuration and 192 GB cap.
Input IDs are identical to the earlier corpus; KV reuse is zero and TG is 256.

| PR297 / pooled passes 2-3 | 2K PP tok/s | 8K PP tok/s | TG tok/s | Four-request wall s |
| --- | ---: | ---: | ---: | ---: |
| Off | 92.51 | 171.85 | 22.30 | 160.01 |
| **On** | **111.09** | **174.16** | **22.31** | **148.25** |
| Off-repeat | 93.25 | 171.38 | 22.33 | 159.55 |

Relative to the two controls, 2K PP improves **19.1-20.1%**, 8K PP
**1.3-1.6%**, and suite wall time falls **7.1-7.3%**. TG is unchanged
(-0.09% to +0.03%). No 2x speedup is observed on this workload/hardware.
All basic checks pass, with no OOM/kills and no CPU quota; minimum sampled
free VRAM is 572.7 MiB. Memory reaches the 192 GB cap with reclamation.

Unlike the frozen-profile numerical test, generated IDs differ between all
three cache-adapting throughput runs, **including off vs off-repeat**. Therefore
these performance outputs are not a bitwise-parity test or evidence of equal
quality. The numerical exactness claim is limited to the separate checks above.

Artifacts were copied into ignored logs from worker directories
`maya-pr297-verify-wrv7v-x8qkk` and `maya-pr297-aba-9kh4h-h2ss9`, under
`/srv/ml/maya-gfx906-tests/`; see `pr297-experiment.json` and
`maya-pr297-aba-9kh4h-comparison.json`. No weights or binary logit dumps were
copied. PR377 flow validation follows separately, not stacked with PR297.

## PR377 flow-path investigation

PR377 (`2b728d504297ac95f78483bd9eabd1da9c42ddcd`) applies cleanly to
v1.1.22 with the same gfx906 fixes and max-ILP flags. Adapted patch SHA256:
`65ad713435d990890ad16fce655c56b398927e46f5504c131b220ba9b5b2d84d`.
This is separate from PR297, not a combined image.

- Runtime `v1.1.22-rocm-10.1-max-ilp-pr377`:
  `sha256:7622b6332d814ab65639a8cc59d6e83e287f1efc19810b7d342b9c68f5fd7eb1`.
- Test `v1.1.22-rocm-10.1-max-ilp-pr377-test`:
  `sha256:a73e8f68c2ff3d44e6b40821786e88eb50ad4519434a5d4a4c67fc20bb4da777`.

Job `maya-pr377-verify-htn2f` completed with exit 0. Compile provenance,
51 Python tests, wave64, the selected CTest suite (22 pass / 3 skip),
620 expert parity comparisons and prefill-stats test passed. DS4 binary SHA256:
`5a4acceeebf340b544bf258cdd1da026c2253a5ae4f2a614547316975bdfdc8d`.
Two original-source runs and patched flow-off were bit-identical on the same
512/2K/8K input/64-row/full-vocabulary numerical test used for PR297.

With `DS4_FLOW_TP=1`, logs confirm **TP2, two NUMA RAM parts, active flow,
and nonzero RAM streaming on all four GPUs**. All logits are finite and basic
checks pass, but flow vs batch is **not bit-identical**:

| Input | Prompt-last KL, flow vs batch | Prompt-last KL, chunk2048 vs4096 control | Identical greedy prefix /64, flow |
| --- | ---: | ---: | ---: |
| 512 | 0.001131 | 0.000735 | 43 |
| 2048 | 0.000939 | 0.000629 | 41 |
| 8192 | 0.0000127 | 0.000125 | 37 |

The maximum KL over rows with still-identical token history is
0.0288/0.0686/0.1253 for flow; the chunk control gives 0.1195/0.3475/0.1704.
Changing chunk also changes expert placement, so this control is a comparison
of numerical scale, **not an acceptance threshold or proof of equal quality**.
The Job's exit 0 means the experiment completed, not that bitwise parity passed.
No OOM/kills occurred under the retained 192 GB cap.

### Isolated file/RAM-copy parity

The additional source-only check (`bench/ds41-flow-copy-parity.py`) completed
successfully in Job `maya-pr377-flow-copy-verify-hdjtt`: same flow/TP2/
chunk4096/resident expert placement, but expert sources are files, one NUMA
RAM part, then two NUMA RAM parts. All **129280 logits at the final prompt
position on each 512/2K/8K input are bit-identical across all three sources**.
Logs confirm active file reads or RAM reads and the requested NUMA count.
Resident expert counts agree: 2891 per member in group 0, 2898 in group 1.
TG1 excludes CPU decode reduction differences; its reported sampling-only
tok/s values are not decode-throughput measurements. This isolates the TP
RAM-copy fix and passed the gate for throughput tests. General flow-vs-batch
quality remains unproven: the earlier non-bitwise result is not superseded.

### Flow off/on/off throughput

Job `maya-pr377-aba-cjbfc` completed with exit 0. Three passes per engine,
normal adaptive expert cache, no logit dumps/profiling, same 56 CPU threads,
TP2/chunk4096/ring400/reserve896/swizzle/RAM-copy configuration. Both variants
set `DS4_CHUNK_MIN=256` and `DS4_PATH_PICK=0` to remove path calibration as a
variable; `DS4_FLOW_TP=0/1/0` selects the tested path. No PR297 patch is present.

| Flow / pooled passes 2-3 | 2K PP tok/s | 8K PP tok/s | TG tok/s | Four-request wall s |
| --- | ---: | ---: | ---: | ---: |
| Off | 93.40 | 171.06 | 22.25 | 159.72 |
| **On, PR377** | **106.39** | **179.52** | **22.46** | **148.98** |
| Off-repeat | 91.55 | 168.51 | 22.24 | 161.78 |

Compared to the two controls, flow improves 2K PP **13.9-16.2%**, 8K PP
**4.9-6.5%**, and reduces suite time **6.7-7.9%**. TG is about **1% higher**;
this small change may include run/cache variation. The on variant improves
between passes 2 and 3, so the pooled result is not a steady-state guarantee.
This is useful enough to test PR360's pump separately, not to combine claimed
speedups with PR297. PR297's 148.25 s suite and this flow run's 148.98 s are
close, but came from separate Jobs and are not a controlled head-to-head.

Input IDs matched the earlier corpus, all measured requests had zero KV reuse
and TG256, and both basic checks passed for all engines. Minimum sampled free
VRAM is 572.7 MiB, the 192 GB cap is reached with reclamation, no OOM/kills,
and no CPU quota. These adaptive-cache performance runs do not prove numerical
equivalence; use the separate checks and their stated limitations.

Artifacts: ignored local directories `maya-pr377-verify-htn2f-5r7gt`,
`maya-pr377-flow-copy-verify-hdjtt-msltq`, `maya-pr377-aba-cjbfc-74hm9`, copied
from `/srv/ml/maya-gfx906-tests/` on the worker; metadata in
`project-maya/logs/flow-experiments.json` and performance report
`maya-pr377-aba-cjbfc-comparison.json`. PR360's completed follow-up is below;
defaults and existing services remain unchanged.

## PR360 flow-pump follow-up

The third image contains PR377 plus PR360
(`db703e9e84f4bf01431ea85aeda77e2ca918fd4c`), not PR297. Combined patch SHA256:
`1e3a25e7b9c1a2c03e28011349e2286908a1d51f252c62bdb4db29e4cdf7d2b3`.
The source remains pinned v1.1.22 with unchanged gfx906 fixes and max-ILP.

- Runtime `v1.1.22-rocm-10.1-max-ilp-pr377-360`:
  `sha256:b7140b5c3f71c24f954e4145941129c0449c04766add18a87119574e23106e2d`.
- Test `v1.1.22-rocm-10.1-max-ilp-pr377-360-test`:
  `sha256:e2e22cb82ef4de8689180170f00a497ad007bd09ef67f3b58696c38123ce39d9`.

### Numerical checks

Job `maya-pr377-360-verify-mnzz5` completed with exit 0. Compile proof
confirmed all 104 HIP units, gfx906, max-ILP and the combined patch hash;
stamp `src=3839d025dc8e258f`, DS4 binary SHA256:
`09bd6d0c6af21d12620a41d33804f533cca81e56216f89e953ea8386f394ad50`.
The 51 Python tests, wave64 probe, selected CTest suite (22 pass / 3 skip),
620 expert parity comparisons and prefill-stats test passed.

The reference binary is **PR377 with flow on**, not the original batch path.
Two reference runs, combined patch with pump off, and combined patch with
pump on all produced **bit-identical 64 x 129280 logits for each 512/2K/8K
input**, with zero max error/KL and 64 identical generated IDs. Fixed initial
expert profile, no expert-cache swaps, TP2/chunk4096/ring400, two NUMA RAM
parts; diagnostic logs confirm flow. Thus this bounded test finds no additional
numerical change from PR360. It does not remove the flow-vs-batch differences
or establish general equal perplexity/quality.

### Pump off/on/off throughput

Job `maya-pr360-aba-9mtf9` completed with exit 0. Same three-pass persistent
engine corpus, normal adaptive expert cache, TP2/56 CPU threads/chunk4096/
ring400/reserve896/swizzle/RAM copies. Flow stays on for all three engines;
only `DS4_FLOW_PUMP_WAIT=0/1/0` changes. `DS4_CHUNK_MIN=256` and
`DS4_PATH_PICK=0` stay fixed; no profiling or logit dumps in this benchmark.

| Pump / pooled passes 2-3 | 2K PP tok/s | 8K PP tok/s | TG tok/s | Four-request wall s |
| --- | ---: | ---: | ---: | ---: |
| Off | 106.92 | 179.48 | 22.49 | 148.64 |
| **On** | **110.11** | **183.16** | **22.28** | **146.49** |
| Off-repeat | 105.03 | 178.67 | 22.18 | 150.52 |

Relative to both off controls, pump improves 2K PP **3.0-4.8%**, 8K PP
**2.0-2.5%**, and reduces suite time **1.4-2.7%**. Prompt time falls
2.5-3.7%. TG varies -0.94% to +0.47%; no decode gain is established.
The author-reported 7-9% prefill gain is not reproduced on these MI50s.
The first off control agrees closely with the previous PR377 on run
(148.64 vs 148.98 s); normal sequential run/cache variation still applies.

All input IDs match, measured requests have zero KV reuse and TG256, and
all basic checks pass. Minimum sampled free VRAM is 572.8 MiB; all variants
reach the 192 GB cap with reclamation, with zero OOM/kills and no CPU quota.
No quality claim is derived from cache-adapting benchmark outputs.

Artifacts copied from worker directories `maya-pr377-360-verify-mnzz5-pkv8k`
and `maya-pr360-aba-9mtf9-sfwdj` into ignored local logs. Metadata:
`flow-experiments.json`; report: `maya-pr360-aba-9mtf9-comparison.json`.

### Final disposition

- **Conservative experimental candidate: PR297 batch**, with
  `DS4_SKIP_UNPICKED=1`, `DS4_FLOW_TP=0`, the existing TP2/56-thread/
  chunk4096/ring400/swizzle/reserve896/RAM-copy settings. Its bounded check
  matches original batch logits exactly and its suite is 7.1-7.3% shorter.
- **Alternative: PR377+PR360 flow**, `DS4_FLOW_TP=1`,
  `DS4_FLOW_PUMP_WAIT=1`, `DS4_CHUNK_MIN=256`, `DS4_PATH_PICK=0`,
  `DS4_SKIP_UNPICKED=0`. Source-copy correctness and pump parity passed the
  stated checks, but flow-vs-batch is not bit-identical and general quality
  equivalence remains unestablished.
- Pump-on's 146.49 s vs PR297's 148.25 s is only about 1.2% less time in
  separate Jobs, not a controlled head-to-head or a proven significant win.
  Do not stack PR297 and flow gains or change defaults based on that ranking.

All experiments are finished. At completion all four GPUs were idle at
10.46 MiB used each; existing llama-server/ComfyUI containers were Running
with zero restarts. No existing service, read-only weight snapshot, default
source SHA, default HIP flags or standard image tag was changed.

## Scope

No full-size weights were downloaded: the DeepSeek Q8 smoke reused cached files.
Full-model DeepSeek text API serving and the four-card layer split now have a
basic successful test. This does not validate full-model GLM, general model
quality/perplexity, prompts longer than 8192 tokens, vision, speculative
decoding or globally optimal performance. TP 2 now has a successful basic
full-model test and the bounded numerical comparisons above, but not a general
quality/perplexity evaluation.
