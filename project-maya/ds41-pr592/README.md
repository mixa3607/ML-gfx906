# DeepSeek-V4.1: v1.1.34 versus PR #592 on gfx906

**Outcome:** baseline TP2 works; PR #592 enables peer transport but times out on
the first PP2048 request. No valid PR speed measurement was possible.
See [RESULTS.md](RESULTS.md) for the baseline table, failure diagnostics and
limitations. Both test pods were removed and all four GPUs returned to 0% use.

## Agreed scope

- Four MI50 32 GB GPUs on `kube-worker6.arkprojects.lan`, two TP2 groups.
- Base settings: the frozen [`values.dspark.yaml`](values.dspark.yaml), originally
  `/home/mixa3607/k3s/kube/apps-ml/maya/values.dspark.yaml`.
- Approved changes: `--tp 2` and `DS4_DRAFT_DEV=0,1,1`. Drafter indices are
  **members of its TP group**, not global GPU IDs; `1,2,3` cannot load at TP2.
- Keep context capacity 196608, prefill chunk 2048, DSpark on, vision on,
  56 CPU threads, reserve 512 MiB, mmap off, and the 220 GiB memory limit.
- First pass a baseline model-load/native-generation gate. Do not score that
  request or start benchmarks before the gate succeeds.
- Then compare input lengths 0/4096/8192/16384 with TG256. The native engine
  rejects empty token lists; the zero-context case needs a minimum seed, whose
  actual token count must be reported. Retain natural EOS/incomplete samples.
- Reuse existing model/vision/drafter files read-only. Each engine gets a private
  copy of the same small expert-profile seed; no weights are copied/downloaded.
- Create only task-specific pods in `apps-ml`; remove them after collecting
  evidence. Do not modify production values or other workloads.

## Sources and builds

| Arm | Source | Image |
| --- | --- | --- |
| Baseline | v1.1.34, `b04264526e93a3c7d3c051cb9cec97af86ae8a37` | `docker.io/mixa3607/maya-gfx906@sha256:bba79624f54d4a1e59c6d66c0d39e0b8afcee3194ec688e54b485626b942994a` |
| Candidate | PR head `9a0876f5861de25f4cb56b7e19e1c8b63704dcda` | `registry.arkprojects.space/apps/maya-gfx906@sha256:3063e35de96907d8624df4f2a6ebf0905fd56de168cf6583762b25134ae903a5` |

The PR head differs from the release only by PR #592 and an intervening
CHANGELOG-only commit (`249f9a8`). Both arms retain the existing gfx906 signed-zero
patch and max-ILP HIP compilation flags. Candidate builds use the normal Maya
entry point and existing remote buildx builder, publish only a private `-pre`
tag, and pin the ROCm 10.1 base manifest. No release presets/workflows change.

PR #592 is opt-in: candidate runs must set `DS4_HIP_PEER_AR=1` and verify
`exact peer prefill all-reduce enabled` for both TP2 groups. A silent fallback
is **not** a measurement of peer transport. AR2/flow paths are not eligible.

## Evidence

- `runtime.json`: effective settings, before private per-run profile paths.
- `pod.baseline.yaml`: isolated startup pod, model/PVC mounts read-only.
- `prepare.sh`: reuse the existing pack without editing it.
- `startup.py`, `startup-case.json`, `startup-output.txt`: unscored startup gate.
- `baseline-provenance.json`: published image build provenance.
- `hardware-*.json`: CPU/GPU inventory and topology before the run.

## Benchmark protocol

Use one persistent native engine per series, 12 distinct PP2048/TG256 warmups,
then PP4096/8192/16384 twice, then two BOS-only/TG256 requests. Use identical
frozen input IDs and a fresh copy of `seed-profile.bin` at every start. DSpark
and the native suffix lookup remain enabled as in the base configuration;
draft counters and generated IDs are retained. This is not the speculation-off
protocol in `../benchmarking/README.md`.

Native PP throughput is `PP / prompt_seconds`; native decode throughput is
`(TG - 1) / decode_seconds`. The latter follows the first-token convention and
is labelled separately from the engine's printed `TG / decode_seconds` rate.
Delivery timestamps may batch speculative tokens, so they are not per-token
latencies. Score only complete TG256 requests after all 12 valid warmups; pool
tokens over time, not arithmetic averages of rates. Context-zero PP throughput
is not meaningful: report the one-token seed and decode speed instead.

Planned series order: baseline A, PR B, fresh baseline A2. Filesystem caches
may survive engine/pod restarts; these are warm-cache measurements, not cold
load benchmarks. The seed is the existing deployment profile captured for this
experiment, not a newly downloaded upstream default.

### Rejected initial attempt

`attempt1/` retains the original interleaved context order and partial baseline.
All 12 warmups and the first BOS-only request reached TG256, but the following
PP4096 reused a **one-token checkpoint**. `SLOT_KEEP=0` disables stored slots,
not the current conversation's checkpoint restoration. The harness rejected
the request and stopped the engine; no result from that series is scored.

Before measuring the PR, both BOS-only cases were moved to the end. All prompt
IDs remain unchanged. This order change prevents the position-1 checkpoint from
feeding a later prose request; it was not selected for speed. The new ordered
case hash is frozen in `cases.manifest.json`, and zero reuse remains mandatory
for every request. The baseline is restarted from the original seed.

## Startup gate

Baseline passed: 250.80 s load, actual TP2 on all four devices, context 196608,
all 10218 CPU-lane experts in RAM, native vision advertised, and a PP2048/TG32
request completed without KV reuse. The output is coherent Russian text.
The engine exited with code 0; cgroup OOM counters stayed at zero. This is a
startup check, **not** a scored performance result or an image-inference test.
See [`startup/result.json`](startup/result.json) and
[`startup/engine.log`](startup/engine.log). rocBLASLt printed missing gfx906
library warnings; generation nevertheless completed through the available path.

The candidate image built successfully on the remote builder. The exact test tag
is in `candidate-image.txt`; build settings/output are retained in
`build-pr592.sh` and `build-pr592-output.txt`.

Baseline A executed all 20 requests. All prose measurements reached TG256 with
zero KV reuse; BOS-only requests stopped naturally at TG135 and TG165. Those
two are retained but cannot provide a TG256 throughput result. No EOS override
or replacement prompt was introduced.

The rejected attempt and A used identical warmup inputs/settings but did **not**
produce identical output IDs despite greedy sampling and seed 1. Thus token
differences against the PR cannot alone establish a PR correctness regression.
The fresh baseline control is needed to expose run-to-run throughput variation,
especially for content-dependent DSpark decode. No deterministic-output or
statistical-significance claim is made.

Final status: baseline A collected (TG256 complete for 4K/8K/16K only), candidate
runtime gate failed, PR benchmark and A2 not run. No speedup claim is possible.
