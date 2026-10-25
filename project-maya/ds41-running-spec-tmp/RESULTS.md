# DSpark coarse screen: blocked by OOM, no usable comparison

## Outcome

The approved screen did not produce an exported, valid A/B/C comparison.
Do not infer a DSpark speedup, slowdown, acceptance rate or incompatibility
from this attempt. No serving manifest was changed and no automatic retry,
memory-limit increase or switch to mmap was made.

At **2026-10-25 21:20:21 UTC**, the kernel reported a memory-cgroup OOM for
test pod UID `c6ac8b09-2cc7-4300-b1b1-667a64244cc5`. Usage and limit were
both **209715200 KiB (200 GiB)**. Kubernetes recorded the container as
`OOMKilled`, exit 137, finished at 21:20:30 UTC. The OOM killed the complete
container process group, including the supervisor and stdout attachment.

The cgroup's last kernel accounting was:

- anonymous memory: 205550149632 bytes (~191.43 GiB);
- file memory: 8583254016 bytes (~7.99 GiB), almost entirely shmem;
- kernel memory: 614961152 bytes (~0.57 GiB);
- this was a cgroup limit failure, not evidence of host-wide RAM exhaustion.

The exact active A/B/C mode at OOM is **not established** by the retained
evidence. `screen-output.txt` only proves A was started. An earlier progress
message attributed the OOM to A before any requests; that attribution was too
strong and is withdrawn. Native results and mode manifests were not exported
before the kill, so even whether earlier modes completed cannot be verified.

## Why measurement evidence is missing

The first local `kubectl exec` tool call used a 120-second timeout. Its client
connection ended while A was loading; the remote Python supervisor and engine
continued. `attach.py` opened the existing supervisor's pipes to keep readers
present and awaited its PID without restarting inference. However, those pipes
also had the original runtime reader: the attachment was not a reliable tee
and did not recover progress output. Its own process was killed by the OOM.

Raw results were only written inside the test pod's private `emptyDir`.
Kubelet cleaned those volumes after container termination, before evidence
could be exported. Read-only inspection through hostPID `rocm-toolkit-0`
confirmed the pod directory remained but its emptyDir contents were gone.
This is a test-harness durability failure, not a model result.

Before another GPU run, change orchestration so progress, completed requests
and raw logs are exported continuously outside the test container's failure
domain. Do not depend on a second reader of the same pipe or on exporting an
emptyDir only after completion. Any changed RAM cap or expert loading policy
requires a revised approved comparison; apply it identically to all modes.

## Frozen experiment and retained evidence

- Image: `docker.io/mixa3607/maya-gfx906:v1.1.28-rocm-10.1`, resolved digest
  `sha256:3cf3dba357c941a190630b0fcf33efd501fe693d9510fa7332522f4b072e30d3`.
- Source commit read from the image:
  `6afa525bbabc3a8f5fd165f89e9bc72155d9bd39`.
- Four MI50 32 GB; hardware inventory is retained in `hardware-*.json`.
- Baseline requested settings: `baseline.json`, TP4, context196608, CPU56,
  chunk4096, reserve1280, mmap-experts off, native vision on, no skips.
- Modes: A none; B on/default placement; C on/`DS4_DRAFT_DEV=1,2,3`.
- Six frozen PP2048 cases, greedy/non-thinking, TG256, natural EOS; three
  warmups and three scored cases per start, same order and profile seed.
- Cases SHA-256:
  `946bb7aaf184329fb15cc0330fbcecc7cc67ea090bfcda05a1b84002f9fd6b80`.
- Source corpus SHA-256:
  `3fd55e2bbdcc948242033959693152faa70672616196a4446a864959529b5fac`.
- Deployment expert-profile seed SHA-256:
  `bcfd7697fc070b0ebcb0138c0ef029429ea0d4ff81ca60eeb7804e08efd0cd29`.
- Drafter snapshot: `d1fc01009f21e26157acb6858c315d0365483b72`.
  BIN SHA-256:
  `42df65159f980a9189d80597e42b30012c7b10e0dd385a47051f3b2fd659bb7b`;
  JSON SHA-256:
  `639c3144bca8cfe4db59057047dca40411f0cc732796e2a9321feb98fee2295f`.
- Pack preparation succeeded with **1245 `mtp.*` tensors** after the JSON
  symlink workaround described in README.md. Index hashes are retained in
  `pack-manifest.json`; the complete temporary pack was not exported.
- `pod-start.json`, `pod-after-failure.json`, `events.json`, `oom-evidence.txt`
  and `gpu-after-failure.txt` preserve the independent failure evidence.
- `cases.jsonl`, `cases.manifest.json` and `sources.jsonl` were exported before
  inference. Sources retain Wikipedia revision links, attribution and CC BY-SA
  4.0 license metadata; generated excerpts follow that license.

## Validation and cleanup

Six CPU-only unit tests passed (protocol validation, reuse/EOS rejection,
OOM/throttling/skipping/timing rejection, pooled scoring and token comparison).
Python compilation, shell syntax and frozen-corpus/hash checks passed.
No completed GPU throughput or correctness check is claimed.

After failure, all four AMD GPUs returned to 0% and approximately 10 MB used
each (`gpu-after-failure.txt`). Production `maya-ds41-decode` remained at zero
replicas (`deployment-replicas-after.txt`). The failed temporary pod was then
deleted within the approved cleanup scope; see `cleanup.txt`.
