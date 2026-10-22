# Project Maya gfx906 (experimental)

[Project Maya](https://github.com/mw00/project-maya) v1.1.21 for Vega20 / MI50 / MI60.
Includes the HIP `maya` (GLM) and `maya-ds4` (DeepSeek) engines and the Python
dashboard/API. Models are **not** included or downloaded at container startup.
Vision helpers and PyTorch-based model conversion are not included.

## Compatibility

[PR #245](https://github.com/mw00/project-maya/pull/245) was merged in v1.1.20.
Its wave64 compatibility layer is already present; do not apply the PR again.
Our [patch](build-context/patch/gfx906.patch) adds gfx906 to the CMake and
installer wave64 lists, enables Vega20's signed `dot4` instruction, and preserves
the signed zero in its INT8 latent-cache reads (verified by `glm_lat8_test`).

Important details:

- Build for **gfx906**, not gfx908; do not spoof the GPU with `HSA_OVERRIDE_GFX_VERSION`.
- `STRATA_HIP_WAVE64=1` must reach the HIP compatibility headers. This enables
  logical 32-lane shuffles/ballots and coherent mapped host allocations for the
  CPU/GPU doorbells. Merely bypassing the wave-size check is not sufficient.
- Vega20 has no WMMA/MFMA. The portable/F32 attention paths are intentional;
  RDNA-only fused/WMMA tests can report skips. Do not force those paths on.
- Keep `STRATA_PREFILL_MMQ=ON` and `STRATA_NATIVE_EXPERTS=ON`: the HIP engine
  requires the pinned llama.cpp MMQ sources. No PyTorch or Triton is needed.
- Use the gfx906 ROCm base, which supplies the matching rocBLAS kernels.
  hipBLASLt tuning tables for Radeon GPUs must not be reused on MI50.
- Mapped host allocations are made coherent by upstream's wave64 layer.
  `HSA_FORCE_FINE_GRAIN_PCIE` is not forced by these scripts.
- Provide `/dev/kfd`, `/dev/dri`, shared memory, and permission to lock host RAM
  (`IPC_LOCK` or an adequate memlock limit). Docker's `--device` grants device
  access without privileged mode. In this k3s cluster, **hostPath alone fails**
  with `EPERM` on `/dev/kfd` and KFD topology: the test Job uses `privileged: true`,
  matching the existing GPU pods. An AMD device-plugin allocation is the
  alternative to privileged hostPath access.
- In Kubernetes explicitly budget the RAM tier, e.g.
  `--env MAYA_GLM_RAM_GB=32`: upstream's free-RAM detection can see the **host's**
  memory rather than the container limit. Leave additional room for dense weights,
  prompt buffers and packing. GPU access via hostPath is shared, not reserved.

See [VALIDATION.md](VALIDATION.md) for measured results and remaining limitations.

## Build

From this directory, with Docker Buildx and registry credentials:

```bash
source ./preset.v1.1.21-rocm-10.1.sh
export MAYA_IMAGE=registry.arkprojects.space/apps/maya-gfx906
./build-and-push.image.sh
```

The script implements `check`, `build`, and check-then-build (no argument), using
the repository's shared build helpers. It pushes by default and skips existing
tags. `MAYA_FORCE_BUILD=1` forces a rebuild; `MAYA_PUSH=0` loads into local Docker.
By default the tag is `v1.1.21-rocm-10.1-<repo-ref>-pre`.

Options: `MAYA_IMAGE_TAG`, `MAYA_BASE_IMAGE`, `MAYA_BUILD_JOBS` (default 4),
`MAYA_CMAKE_HIP_FLAGS`, `MAYA_BRANCH`, `MAYA_COMMIT`. The source SHA is pinned;
when changing the source tag, also change the SHA (or explicitly set
`MAYA_COMMIT=''` to follow that tag). Patches fail closed on incompatible sources.

The default HIP flags are empty. To build the separate max-ILP scheduler variant
without replacing the baseline image, use a distinct tag:

```bash
MAYA_IMAGE=registry.arkprojects.space/apps/maya-gfx906 \
MAYA_IMAGE_TAG=v1.1.21-rocm-10.1-max-ilp \
MAYA_CMAKE_HIP_FLAGS='-mllvm -amdgpu-sched-strategy=max-ilp' \
  ./build-and-push.image.sh
```

New builds record the flags in `build-hip/MAYA-BUILD.json`; the test target also
contains `CMakeCache.txt` and `compile_commands.json` to check the actual HIP
compile commands. No additional fast-math or weight-quantization option is
enabled by this flag.

The manual [Actions workflow](../.github/workflows/maya-build.yaml) builds either
the runtime or test target. There is no automatic daily publication while this
port is experimental.

## GPU tests in k3s

```bash
MAYA_IMAGE=registry.arkprojects.space/apps/maya-gfx906 \
MAYA_TARGET=test MAYA_IMAGE_TAG=v1.1.21-rocm-10.1-test \
  ./build-and-push.image.sh build
./test-k8s.sh
```

The test target includes build outputs and CTest metadata at their original
paths. The Job matches `apps-ml`'s AMD node selector, GPU tolerations and device
mounts. It does not stop existing workloads, mount model storage or fetch weights.
Jobs have unique names, no retries, a 15-minute deadline and a one-hour TTL.
Logs are saved under `logs/`.

Tests include installer/architecture regressions, a four-logical-warp probe with
different ballots in each wave64 half, upstream HIP/GLM parity tests, coherent
host handoffs, an exhaustive INT8-latent-to-FP16 conversion check, a 256 MiB
mlock check, and the expert-kernel parity sweep.
Missing tests and failed tests are errors; architectural skips remain visible.
This is **not** a claim that the entire upstream suite or a full-size model passes.

The separate [full-model validation](VALIDATION.md#full-model-deepseek-v41-q8-api-smokebench)
also covers real DeepSeek-V4.1 Q8 text API requests on four MI50s, using the
worker's host-local cache (not the shared PVC). `bench/ds41-q8.py` creates an
index pack from `MAYA_BENCH_MODEL`, starts a loopback-only API, runs bounded
requests, saves replies/timings under `MAYA_BENCH_OUT` (default `/results`),
and stops its server. It expects this runtime image, four visible GPUs and
existing GGUF files; it does not download weights.

`bench/ds41-context.py` uses the native engine protocol for exact-length runs:
0 (one BOS), 2048 and 8192 prompt tokens, each followed by exactly 256 output
tokens. Each case starts a fresh engine to avoid KV-prefix reuse, with a fixed
8704-token capacity and EOS stopping disabled. It uses the same model/output
environment variables and conservative four-GPU settings. These are throughput
tests, not normal chat requests or an assessment of the text after EOS.

`bench/ds41-tune.py` keeps an engine alive across a Russian multi-topic suite
(climate, databases, history and ecology): a warmup followed by 2048/8192-token
prompts and TG 256, then two basic answer checks. EOS stopping is disabled to
measure exact output lengths; text beyond EOS is not a quality assessment.
Each launch configuration gets its own process and the same initial expert
profile/corpus/order, but expert caches stay warm between that configuration's
requests. The default sweep compares 48/56 CPU threads with chunk 2048 and a
512 MiB per-card reserve, then tries chunk 8192 with the faster passing CPU
configuration. Maya's chunk option is not a pair of llama.cpp batch/ubatch
settings. No speculation, expert skipping or additional quantization is enabled.

For this cluster, `python3 project-maya/bench/run-tune-k8s.py` launches the suite
on worker6 using the pinned image, a read-only host cache and separate hostPath
results. It has **no CPU quota** and a **192 GB decimal RAM cap** (178.8 GiB),
including cgroup-charged file cache. Existing shared cache pages can have a
different cgroup owner. It does not reserve GPUs through a device plugin: check
that all four MI50s are free first. An explicit sweep can be selected with:

```bash
python3 project-maya/bench/run-tune-k8s.py \
  --configs '[{"cpu":48,"chunk":2048,"reserve":512}]'
```

The launcher streams logs and preserves the Job specification under ignored
`project-maya/logs/`; Job failure is recorded in Kubernetes and the result
summary, not inferred from `kubectl logs` succeeding. CPU/GPU/cgroup samples
are diagnostic, not isolated performance measurements. Comparing cases from
different processes does not flush the host page cache or make them cold runs.

The original [measured tuning results](VALIDATION.md#final-comparison-with-deployment-vram-headroom)
favor **56 CPU threads, chunk 2048, TP 2, `--mmap-experts off`, reserve 896 MiB**
for the tested mix of Russian 2K/8K prompts: about 102 tok/s PP on 2K and
16.9 tok/s aggregate TG. TP 1 retains faster 8K prefill. All remaining experts
fit in RAM under the 192 GB cap, and the increased reserve left at least
roughly 0.5 GiB free per card in the samples. Reproduce that candidate with:

```bash
python3 project-maya/bench/run-tune-k8s.py \
  --configs '[{"cpu":56,"chunk":2048,"reserve":896,"tp":2,"mmap":"off","label":"ram-copy"}]'
```

The TG 256 test ignores EOS; normal serving must keep EOS stopping enabled.
Basic checks passed without changing the weights or skipping experts, but
full-model quality/perplexity and bitwise parity were not established.

For compiler A/B tests, the launcher accepts `--image IMAGE@sha256:DIGEST` and
`--rounds 3`. It performs the warmup only once, then repeats all four measured
topics three times in the same engine process. Requests still have no prompt
KV reuse, but expert caches can improve between rounds; compare corresponding
rounds, not a warmed compiler variant against the baseline's first pass.

The [max-ILP experiment](VALIDATION.md#max-ilp-compiler-experiment) measured
**20.23 -> 22.38 tok/s TG (+10.6%)** over pooled passes 2-3. Prefill did not
improve. A subsequent baseline control returned to 20.13 tok/s, confirming
roughly **11% higher TG**, but essentially unchanged total time for this PP-heavy
suite. The variant is published separately; default flags/image remain unchanged.

The [v1.1.22 comparison](VALIDATION.md#v1122-prefill-experiment) did not establish
a meaningful speedup over v1.1.21 with the same max-ILP/TP 2 settings. Its opt-in
`DS4_HIP_ATTN_SWIZZLE=1` improved prefill about 2% over v1.1.22 without swizzle,
but only brought overall throughput close to the previous release. The separate
profile points primarily to the expert stage and repeated host-expert streaming,
not sparse attention. Image `v1.1.22-rocm-10.1-max-ilp` is available separately;
default source/image/swizzle settings remain unchanged.

A subsequent v1.1.22/max-ILP/TP 2 test with swizzle on and `DS4_RING_MB=400`
found that **chunk 4096 improves 8K PP from 131.71 to 171.66 tok/s (+30.3%)**
over pooled passes 2-3. The mixed suite takes 6.9% less time, with 2.8% lower
2K PP and 1.3% lower TG. Minimum sampled free VRAM is 573 MiB/card with reserve
896 MiB. The completed ring-200/300/400 sweep found no material gain from
reducing ring size: 300 and 400 are effectively tied, while 200 is slower.
The [chunk/ring follow-up](VALIDATION.md#chunk--streaming-ring-follow-up) retains
**chunk 4096 / ring 400** as the experimental mixed-workload candidate; this
does not change defaults. Reproduce it without changing weights or source:

```bash
python3 project-maya/bench/run-tune-k8s.py \
  --image registry.arkprojects.space/apps/maya-gfx906:v1.1.22-rocm-10.1-max-ilp@sha256:5f24929a1a8a5184500a9d764e024581c086e01e0bfdab4ebe83d46b2e746afb \
  --rounds 3 \
  --configs '[{"cpu":56,"chunk":4096,"reserve":896,"tp":2,"mmap":"off","label":"chunk4k-ring400","env":{"DS4_HIP_ATTN_SWIZZLE":"1","DS4_RING_MB":"400"}}]'
```

`MAYA_TEST_IMAGE` and `MAYA_TEST_NAMESPACE` select another image/namespace.
Inside the test image, `HIP_VISIBLE_DEVICES` selects a card and `MAYA_TEST_REGEX`
overrides the CTest selection. For example, to run every registered test manually:

```bash
docker run --rm --device /dev/kfd --device /dev/dri --cap-add IPC_LOCK \
  --security-opt seccomp=unconfined --shm-size 1g \
  -e MAYA_TEST_REGEX='.*' \
  registry.arkprojects.space/apps/maya-gfx906:v1.1.21-rocm-10.1-test
```

### Opt-in PR experiments

`MAYA_EXPERIMENT=pr297`, `pr377`, or `pr377-360` applies a separate patch to
the pinned v1.1.22 source. Keep the original source SHA and max-ILP flags when
building these images; use distinct image tags. Selection and patch SHA256
are recorded in `SOURCE_EXPERIMENT.json` and `build-hip/MAYA-BUILD.json`.
Nothing is applied when `MAYA_EXPERIMENT` is empty (the default).
See [patch provenance](build-context/patch/experiments/README.md).

`bench/run-experiment-k8s.py --experiment NAME --image TEST_IMAGE@sha256:…
--baseline RUNTIME_IMAGE@sha256:…` runs compile-provenance checks, the existing
GPU smoke suite and separate full-model logit comparisons on 512/2K/8K inputs.
It imports only the reference binary through an init container, reuses the
read-only host weight cache, and caps the Job at 192 GB without a CPU quota.
Numerical checks use the same initial expert profile with expert-cache swaps
disabled; this is not the throughput configuration. Full-vocabulary logits
are saved for the prompt's final position and 63 decode positions. Comparisons
after a differing generated token are excluded from numerical metrics because
the token histories then differ. Binary dumps stay on the worker, not in Git.

Throughput comparisons run separately, without logit dumps or profiling, using
the existing persistent-engine corpus. PR #297 changes the batch transfer path;
PR #377 enables testing the distinct flow path safely; PR #360 is tested only
against a correct, useful PR #377 flow baseline. Do not use unpatched
`DS4_FLOW_TP=1` with TP/RAM-copy mode.

The [PR297 experiment](VALIDATION.md#pr297-transfer-pruning-experiment)
passed bit-identical full-vocabulary logit checks at 512/2K/8K with frozen
expert placement. Its subsequent A/B/A improved 2K prefill **19-20%** and
reduced mixed-suite time **7.1-7.3%**, with essentially unchanged TG and only
1.3-1.6% higher 8K PP. It is available as
`v1.1.22-rocm-10.1-max-ilp-pr297`, enabled with `DS4_SKIP_UNPICKED=1`;
global defaults are unchanged. Cache-adapting benchmark outputs vary even
between control repeats; numerical parity refers to the separate frozen test.

The [PR377 flow investigation](VALIDATION.md#pr377-flow-path-investigation)
passed smoke tests and bit-identical prompt-last logits across file sources
and one/two-NUMA RAM copies (`--mode flow-copy`). Flow off/on/off reduced
suite time **6.7-7.9%** versus its batch controls. Flow-vs-batch logits are
still not bit-identical, so this source-copy validation does not establish
equal quality. Its suite time is close to PR297 in separate Jobs, not a
controlled head-to-head. The [completed PR360 test](VALIDATION.md#pr360-flow-pump-follow-up)
preserved exact logits relative to PR377 flow and reduced suite time another
**1.4-2.7%**, not 7-9%. Its image is `v1.1.22-rocm-10.1-max-ilp-pr377-360`,
with flow on, `DS4_FLOW_PUMP_WAIT=1`, `DS4_CHUNK_MIN=256`, `DS4_PATH_PICK=0`
and `DS4_SKIP_UNPICKED=0`. Its advantage over PR297 in separate Jobs is only
about 1.2%, not a demonstrated head-to-head win. Prefer PR297 as the conservative
experimental candidate because its checked logits match the original batch
path; retain the flow image as a separate alternative with the stated quality
caveat. All experiments are complete; no defaults or services were changed.

## Setup and serving

Use a **runtime** image tag, not the test target. Check the card first:

```bash
IMAGE=registry.arkprojects.space/apps/maya-gfx906:YOUR_RUNTIME_TAG
docker run --rm --device /dev/kfd --device /dev/dri "$IMAGE" --check --gpu 0
```

Model setup is explicit and can download roughly 95 GB for Maya-S24. To use
already downloaded GGUF shards instead, mount their writable directory under
`/data` and use `--gguf-dir /data/models/Maya-S24` instead of `--download-model`.
Packs are written beside the shards; do not point setup at a read-only HF snapshot.

```bash
mkdir -p data
docker run --rm --device /dev/kfd --device /dev/dri \
  --cap-add IPC_LOCK --ulimit memlock=-1:-1 --shm-size 1g \
  -v "$PWD/data:/data" "$IMAGE" setup \
  --gpu 0 --model Maya-S24 --models-dir /data/models \
  --context 8192 --no-vision --yes --download-model \
  --env MAYA_GLM_RAM_GB=32
```

Setup reuses the precompiled engine, then copies generated HIP configs into
`/data/config/`. Set `MAYA_CONFIG` to the copied file; for Maya-S24 the upstream
filename is `maya-maya-s24-hip.json`.

```bash
docker run --rm --device /dev/kfd --device /dev/dri \
  --cap-add IPC_LOCK --ulimit memlock=-1:-1 --shm-size 1g \
  -p 127.0.0.1:8080:8080 -v "$PWD/data:/data" \
  -e MAYA_CONFIG=/data/config/maya-maya-s24-hip.json \
  "$IMAGE" serve
```

`serve` starts the upstream server directly without setup or a source refresh.
It listens on `0.0.0.0:8080` inside the container (`PORT` changes the port).
Set an API key during setup with `--api-key`, or pass `--api-key` after `serve`;
do not publish an unauthenticated dashboard externally. `/health` and `/v1/models`
are available once loaded. Models and packs must keep the same container paths
as during setup. Use a new image, not the dashboard's source updater, for upgrades.

For multiple cards pass `--gpus 0,1,2,3` during setup. The engine uses a layer
split and host-memory hops, so P2P is not required. Multi-GPU/full-model validation
is separate from the single-card kernel tests. See also
[docker-compose.example.yaml](docker-compose.example.yaml) and upstream
[AMD notes](https://github.com/mw00/project-maya/blob/v1.1.21/docs/AMD_MAYA.md).
