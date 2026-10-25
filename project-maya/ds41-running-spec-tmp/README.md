# DSpark coarse screening

The first 200Gi attempt failed with OOM; see [RESULTS.md](RESULTS.md).
The approved 220Gi retry completed A/C: **decode +29.7%, scored wall unchanged**;
default-placement B was OOM-killed. See [retry results](retry-220gi/RESULTS.md)
and [retry procedure](retry-220gi/README.md). First-attempt evidence below is
retained without overwriting it. The revised `screen.py` supports either cap;
the original historical runner is in commit `3b1c305`.

Initial 200Gi scope: one temporary pod on worker6; three sequential engine starts
(A: none, B: on/default placement, C: on/DS4_DRAFT_DEV=1,2,3). Each start gets
the same three unscored PP2048/TG256 warmups, then three scored PP2048/TG256
requests. Greedy, non-thinking, natural EOS, no cross-request KV reuse. Only
B/C may speculate. Keep decode.yaml's TP4/context196608/vision/CPU56/chunk4096,
200Gi memory cap and environment. No automatic calibration or parameter sweep.

HF cache and existing deployment data are mounted read-only. The pack, copied
seed profile and per-start profiles live on the test pod's private emptyDir.
The production Deployment stays at zero. No model downloads or weight copies.
Export evidence before deleting the pod and check all four GPUs return idle.

Inputs follow ../benchmarking/CORPUS.md, reduced to three articles per split
and three warmup/three measurement cases. Sources and cases are frozen before
the first engine starts. Source texts are Russian Wikipedia CC BY-SA; per-page
revision links, history/attribution links and hashes are in sources.jsonl.

This is a coarse, order-biased A/B/C screen, not the full benchmark protocol:
three warmups cannot establish steady state, and no reverse-order repeat is
authorized. A >=10% decode gain is a reason for a full A/B, not proof of a
general speedup. Smaller differences are inconclusive. Native protocol timings
exclude HTTP. DSpark emits token bursts: delivery intervals are not kernel-level
per-token latency, so no ITL claim is made. Record native decode timings too.

## Reproduction

`pod.yaml` is a historical test manifest, not a serving deployment. Use
`prepare.sh` inside this pod, then upload `baseline.json`, `corpus.py`,
`sources.jsonl` and `screen.py` into `/data/screen`. Build `cases.jsonl` with
`corpus.py build --source /data/screen/sources.jsonl --out /data/screen/cases.jsonl`
before running `python /data/screen/screen.py`. Export `/data/screen` before
deleting the pod. Run `python summarize.py PATH_TO_EXPORTED_SCREEN` locally.

The drafter snapshot is `d1fc01009f21e26157acb6858c315d0365483b72`.
`prepare.sh` checks its weights and prints their SHA-256. The packer resolves
the JSON's symlink before deriving its sibling `.bin`; HF snapshot symlinks
resolve into unrelated suffixless blobs. A private regular JSON index plus a
symlink to the cached `.bin` avoids that issue without copying model weights.

`screen.py` launches the native engine directly, not maya.py: no automatic
speed calibration or rewriting of serving configuration. Each start receives
the same copied deployment expert profile and writes its own private profile.
The final values in `config.json` plus the pod's fixed environment are the
runtime configuration; inherited environment variables are not exported.

The first local `kubectl exec` connection timed out after 120 seconds while
A was loading. The original Python supervisor and native engine remained alive;
they were not restarted. `attach.py` keeps that supervisor's stdout/stderr pipes
readable and awaits its existing PID via pidfd, with no polling or new GPU run.
`screen-output.txt` and `reattached-output.txt` contain only partial supervisor
output. The pipe attachment was not a reliable tee because the runtime retained
another reader. Per-run files were not exported before OOM; kubelet cleared the
emptyDir after termination. A future harness must continuously export evidence
outside the test container, not just use an unlimited connection timeout.
