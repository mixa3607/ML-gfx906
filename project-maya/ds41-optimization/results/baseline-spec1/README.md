# Baseline attempt: blocked before READY

**No benchmark measurements were produced.** On 2026-10-31 at 23:12 UTC,
Maya rejected the unchanged baseline during startup, before any of the suite's
22 requests. `results.jsonl` is intentionally empty; no throughput or draft
acceptance result can be reported.

## Attempted configuration

- Suite: `project-maya/benchmarking/suites/ds41f-ru-long/cases.jsonl`.
  SHA-256: `3195a02e90078b366c00dce429652b386fe3616d879cdd25c1a6f288435b46c3`.
- Schedule: 12 PP2048 warmups, then PP2048/4096/8192/16384/32768 twice,
  TG256, greedy, thinking off, requested speculation `spec=1`.
- Image: `docker.io/mixa3607/maya-gfx906:v1.1.45-rocm-10.1`, pinned to
  `sha256:50210b2fdec9c2e36b57fe0c8de2d3a9dd2d1fb33bb99757b37f229e824d51d2`.
- Upstream source: `6ecbd3cbc5330b57f70cd5cf8a5c42eb8ef950cc` (v1.1.45).
- Baseline snapshot: [maya-config.json](maya-config.json). Requested TP4,
  context 524288, prefill chunk 4096, DSpark on, CPU threads automatic,
  `DS4_COPY_NUMA=2`, `MAYA_DS4_DRAFT_DEV=1,2,3`, prompt skip 2 and slot keep/cap 1/4.
- Node: `kube-worker6.arkprojects.lan`, four gfx906 GPUs, 76 physical CPU
  cores on two NUMA nodes, SMT disabled, no swap. Pod memory limit: 220 GiB;
  no CPU quota. Actual hardware details are in the metadata files.
- New writable `/data`, fresh expert-profile seed from the image and a new pack
  index. GGUF/drafter blobs and previously prepared vision artifacts were
  referenced without copying or modifying them. Both existing PVCs were
  mounted read-only. No model downloads or image rebuilds were needed.

## Startup failure

[engine.log](engine.log) records:

```text
ds4: tensor parallel 4 -> 2: the experts' 32-value blocks split n_ff 2304 no other way (each GPU its own layers)
maya-ds4: DS4_DRAFT_DEV=1,2,3: not one whole number, or one a block (3), each 0 .. 1 (the drafter's group's members)
```

The upstream `Model::Impl::load` TP admission loop in
[`src/ds4/ds4_model.cu`](https://github.com/mw00/project-maya/blob/v1.1.45/src/ds4/ds4_model.cu#L3421-L3455)
requires the ordinary member FFN width to be divisible by 128, in addition to
the quantization block size. `2304 / 4 = 576` is not divisible by 128, so the
engine reduces the width to 2. The drafter's existing member IDs 2 and 3 then
become invalid. This is not a failure of the speculative request setting:
the engine never reached `READY` and received no `GEN` requests.

The runner consequently exits with `StopIteration` on EOF. No retry with TP2,
drafter relocation, speculative disablement or other fallback was performed.

### Proposed resolution, not applied

`MAYA_DS4_TP_GGUF_UNEVEN=1` enables the upstream whole-quant-block partition
path, whose admission rule does not require the same 128-value divisibility.
For this pack, 72 blocks of 32 divide into four equal 18-block / 576-value
parts. It is a candidate to preserve the requested TP4, **not a verified
successful startup or a bit-exactness result**. Adding it to the baseline and
rerunning needs agreement because it changes the effective execution layout.

## Artifacts and cleanup

- `results.jsonl`: empty output from the failed runner.
- `engine.log`: complete startup stderr and runner traceback.
- `run-metadata.json`: effective arguments/environment, input and engine
  hashes, CPU/NUMA/cgroup details, start/end timestamps and exit code 1.
- `pack-metadata.json`: model revisions/blob identities, generated pack-index
  hashes and the reused vision manifest.
- `expert-profile.seed.bin`, `expert-profile.final.bin`: equal seed/final
  profiles; no requests ran or modified the profile.
- `gpu-static.json`, `pod.json`: hardware and exact pod/image configuration.

The benchmark pod was deleted. A subsequent `amd-smi monitor` sample showed
all four GPUs at 0% utilization with approximately 10 MB VRAM used per GPU.
The 11 local benchmarking CPU tests passed after changing the runner to
`spec=1`. Frozen input cases were not regenerated or modified. No legacy
speculation mode, compatibility option or fallback was added.
