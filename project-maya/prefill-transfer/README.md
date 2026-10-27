# DeepSeek TP4 prefill transfer experiment

Status: completed on 2026-10-27. The transfer patch improved warm prefill about
2.2x on the tested four-MI50 configuration; transfer pruning did not help.
See [RESULTS.md](RESULTS.md) for measured tradeoffs and bounded validation.

## Scope

- Upstream v1.1.30, `8621e33159f426da2d376be4ec012b0ce8fe2948`.
- Existing gfx906 patch set, unchanged.
- PR [520](https://github.com/mw00/project-maya/pull/520), pinned at
  `b5eb8ca76cce399121d1a15c7cc0f42895483c72`: only compact TP-member
  prompt transfers, direct DMA from pinned RAM copies, and the associated
  load-time transfer checker. No new model, quant format, or arithmetic.
- The transfer check reads its reference from the original model file, rather
  than another RAM copy. Check both direct DMA and `DS4_COPY_PIN=0` fallback.
- Subsequently port PR [297](https://github.com/mw00/project-maya/pull/297),
  pinned at `6f72b39cd0a793f5e4cd6037d37fe348dc7cdc4d`, to the compact
  transfer path. Keep pruning opt-in and validate actual skipped transfers.

## Controls and safety

Four MI50 32 GB on worker6; TP4, DSpark on with blocks on devices 1/2/3,
context196608, CPU56/NUMA2, reserve512, ring400, Engram256, vision on,
all CPU experts copied, 220Gi memory limit, no CPU quota. Approximate skips
and cross-request KV reuse are disabled. Preserve the deployment's image,
configuration and private initial expert-profile seed.

The serving deployment is stopped only for GPU testing, then restored to its
original replica count. Test pods mount the existing data and HF PVC read-only;
only small metadata and the expert-profile seed are copied into test storage,
never model/Engram/vision/drafter weights. No models are downloaded.

Diagnostics use the native TP/byte checker, swap checks and finite logits,
separately from timing. Timing starts each engine from the same frozen seed,
with 12 distinct PP2048 warmups followed by six distinct PP2K/4K/8K TG256
requests. DSpark remains enabled in every timing arm. Natural EOS is retained
as an incomplete TG256 sample, not replaced or extended.

Compare stock A, transfer B, fresh stock A, then pruning disabled/enabled on
the same patched build, and chunk2048/4096 separately. Record PP, decode,
complete-request wall, acceptance, RAM, OOM/throttling, input hashes and
actual TP4. Logs/results must stream to the local machine before test cleanup.
The frozen corpus is the previously archived Russian suite; this is development
timing, not an untouched holdout or long-context/vision quality certification.

## Build

From the repository root, source `.build/.env-local.sh`, override `RVS_PUSH=0`
and `TB_PUSH=0`, and use the existing remote builder. Set:

```sh
export MAYA_BRANCH=v1.1.30
export MAYA_COMMIT=8621e33159f426da2d376be4ec012b0ce8fe2948
export MAYA_PATCH=v1.1.30-transfer
export MAYA_PRESET_NAME=v1.1.30-rocm-10.1-transfer520
export MAYA_CMAKE_HIP_FLAGS='-mllvm -amdgpu-sched-strategy=max-ilp'
export MAYA_BASE_IMAGE=docker.io/mixa3607/rocm-gfx906:10.1-complete
export MAYA_IS_RELEASE=0 MAYA_PUSH=1
export REPO_GIT_REF=20261027-pp01
./project-maya/build-and-push.image.sh build
```

This publishes only a private `-pre` tag. Public tags and CI are unchanged.
The private ROCm 10.1 base tag was absent; both builds used the existing public
10.1 base, index `sha256:b1d72163863a56b6b2bf498d159c1dc17627f8751aed6c8b8de2ebe9882972b4`.

Built experiment images (private index digests):

- transfer520: `sha256:a620d20efd4c717bc97f5cc8916c117fe5b30f4015c2d8d302dfadac108b9550`
- transfer520-prune297: `sha256:488bc84ebb935fed13cd396157060f3fbbbca08387a561aaf17d9ae46ceacc08`

## Local validation

`python3 -m unittest discover -s project-maya/prefill-transfer -p 'test_*.py' -v`
passes 9 tests. The reader test extracts the actual `read_mx_member` and
`mx_down_member` implementations from the distributed patch, compiles them
with AddressSanitizer/UndefinedBehaviorSanitizer, and checks 480 independent
row-copy cases: TP1/2/4/8, NUMA1/2, RAM and file sources, rotated unequal
blocks, real 5120-wide geometry, and destination guards. This is CPU-only
layout validation, not a replacement for GPU DMA or full-model checks.

The collector tests cover successful fsync/ACK persistence, nonzero-exit
evidence preservation, invalid artifact paths and incomplete zero-exit runs.

## Reproduce the experiment

`prepare.py OUTPUT` captures the current serving configuration, expert-profile
seed and immutable image identity and writes a test-pod manifest without
changing Kubernetes resources. `orchestrate.py --root OUTPUT --transfer-image
IMAGE@sha256:... --prune-image IMAGE@sha256:...` performs the serial runs and
cleanup. It modifies the deployment scale and test pods, and runs real GPU
workloads: obtain task-specific approval before invoking it. The initial
serving pod name in `prepare.py`/`orchestrate.py` belongs to this captured run;
update it deliberately for a future deployment, not by guessing a pod.

`analyze.py OUTPUT` independently verifies complete timing arms and recomputes
pooled metrics. Native decode uses `(TG - 1) / decode_seconds`; DSpark token
delivery events can contain bursts and are not individual-token ITL.
