# DeepSeek-V4.1: measured prefill/decode profiles

Two alternative, complete application manifests for **4 × MI50 32GB (gfx906)**
on `kube-worker6.arkprojects.lan`. Each includes a ConfigMap with the engine
JSON and preparation/start scripts, a persistent data PVC, a Deployment with
CPU-only preparation in an init container, and a ClusterIP Service.

## Files and measured results

| File | Profile | PP2K / PP4K / PP8K, tok/s | Aggregate PP, tok/s | TG, tok/s | Scored wall, s | Container RAM cap |
| --- | --- | --- | ---: | ---: | ---: | --- |
| [`prefill.yaml`](prefill.yaml) | TP2, whole-block flow, pump1 | 106.61 / 133.62 / 182.65 | **151.36** | 21.866 | 259.420 | 187Gi |
| [`decode.yaml`](decode.yaml) | Genuine TP4, whole-block, no flow | 87.66 / 139.42 / 147.68 | 132.48 | **27.492** | 272.093 | 199Gi |

These are the best **measured aggregate prefill on the 2K–8K development suite**
and **measured decode**, not universal optima or a fresh comparison between
these two files. Each result excludes startup and 12 distinct warmup requests;
six scored requests used one request at a time, TG256, greedy non-thinking,
complete PP including chat template, no KV reuse/speculation and no logit dumps.
Rates pool tokens/time. Sources: [full experiment history](../ds41-running-tmp/RESULTS.md),
Approach 5 (flow/pump1 warm timing) and Approach 6 (final matched TP pair).

- **Prefill caveat:** flow/pump1 passed bounded 64K retrieval and vision, but its
  dump-enabled 64K prefill took 393.034s versus 270.726s for the earlier stock
  TP2 diagnostic. This profile is for short prefill, not a fastest-64K claim.
- **Decode caveat:** TP4 passed four-member native numerical checks and 512
  finite full-vocabulary logit rows. Its separate matched TP2 control achieved
  TG 21.988 and total wall 269.508s: TP4 improved TG 25.0% but not total request
  time (+1.0%). **TP4 64K/vision inference was not validated**; enabling vision
  and allocating context 196608 are not proofs of either. TP4 load OOMKilled at
  187Gi and 190Gi; do not lower its memory cap based on the TP2 result.

The conservative full-range recommendation remains stock TP2 with flow/YOCO
off. These two files intentionally preserve the requested specialist cases.
Final holdout was not run. The Kubernetes packaging itself has only CPU/client
validation, not a new deployment, HTTP benchmark or GPU compatibility test.

## Fixed software and settings

- Image: `docker.io/mixa3607/maya-gfx906:v1.1.27-rocm-10.1`, pinned in both
  containers by index digest
  `sha256:d46312703b79af1cd70174ae9ef2faee23875db9c51f90353424aba6101ac2c1`.
  Source: `4615f346d9311dd1ce9f5738ab04446f023a6e42`, gfx906 build fingerprint
  `8933c5ceb60f89e7`.
- Model: `unsloth/DeepSeek-V4.1-Flash-1017-GGUF:UD-Q8_K_XL`, snapshot
  `60ad3651641b5c97679c807e064ab1d7a3ca1455`. Native vision source snapshot:
  `deepseek-ai/DeepSeek-V4.1-Flash-1017`,
  `1bae0e1088993b9b82de08f59de5be5a34e42170`.
- Both: CPU56, NUMA2 full expert copies, chunk4096, Engram256MiB, ring400MiB,
  reserve1280MiB, context196608, native vision on; YOCO, expert skips, retained
  conversation slots and DSpark off. No extra quantization or history truncation
  is introduced by the manifests. GPU indices are 0–3; there is **no CPU quota**.
- The init container checks source, pack metadata and original expert seed
  hashes. Model blobs stay in the read-only HF cache; `/data` holds the small
  index/tokenizer, converted vision tower, logs and separate adaptive profiles.
  Profiles start from the tested shipped seed and persist across restarts;
  runtime warm state therefore need not match the benchmark's fresh starts.
  The server's writable config is copied out of the read-only ConfigMap.

## Prerequisites

The stand already supplies namespace `apps-ml`, storage class `local-path`,
the populated `worker6-hf-cache` PVC and `harbor-registry-pull-secret`. These
shared infrastructure resources and model weights are **not created** by these
files. The init container fails if cached model/vision inputs are missing;
it never downloads whole model shards. The first vision conversion may make
small, pinned HTTP Range requests for the three marker rows from shard 2
(about 30KB plus its header), even with HF offline flags. Subsequent starts
reuse the converted vision data on the application PVC.

Ensure all four GPUs are free before deployment. HostPath GPU access does not
reserve devices with a device plugin; an unrelated workload can still conflict.
Memory requests equal the measured container caps to avoid scheduling this
large workload as an 8Gi pod. For decode, keep any retained peer-pod charge
below 1Gi to stay within the agreed **200Gi known-pod budget**. Kubernetes
enforces the container cap, not that cross-pod sum: inspect peer usage before
starting. Shared memory and charged file cache count toward the cap.

## Start or switch

Run from this directory. **Choose one file; do not apply the directory or both
files together.** They deliberately use the same object names and one persistent
data PVC. The profile label changes the pod template; `Recreate` terminates the
old serving pod before starting its replacement. This is not a two-server setup.

```bash
kubectl apply -f prefill.yaml
# Or, for decode (also switches an existing prefill deployment):
# kubectl apply -f decode.yaml
kubectl -n apps-ml rollout status deployment/maya-ds41 --timeout=2400s
kubectl -n apps-ml logs deployment/maya-ds41 -c prepare
kubectl -n apps-ml logs -f deployment/maya-ds41 -c maya
```

For changes within the same profile, restart the Deployment after updating its
ConfigMap; ConfigMap changes alone do not roll pods. Inspect `/data/prefill.log`
or `/data/decode.log`: all CPU experts must be copied into RAM, and decode must
show actual TP4 with layers0–39 on every GPU. Missing readiness or a fallback is
not a validated profile. Preparation checks do not rescan all 500GB of weights.

```bash
kubectl -n apps-ml port-forward service/maya-ds41 8080:8080
```

Then use `http://127.0.0.1:8080/v1` (model `deepseek-v4.1-flash`). The Service
is cluster-internal, with no Ingress, NodePort or configured API key; add
authentication before exposing it beyond a trusted cluster/local port-forward.
Probes allow a 30-minute model startup and do not kill long prompts with a
liveness timeout. For API/image usage, see [RUNNING.md](../RUNNING.md).

Stop while retaining the prepared pack and learned profiles:

```bash
kubectl -n apps-ml scale deployment/maya-ds41 --replicas=0
```

Do not use `kubectl delete -f` as a routine stop: it also deletes the application
PVC. The shared HF PVC is never owned or deleted by these manifests.

## CPU-only validation

Requires Python with PyYAML and `kubectl` (client validation reads cluster schema):

```bash
python3 -m unittest discover -s . -p 'test_*.py'
kubectl create --dry-run=client -f prefill.yaml -o name
kubectl create --dry-run=client -f decode.yaml -o name
```

Completed on 2026-10-26: both client validations, four manifest tests (including
embedded JSON/script syntax and equivalence to the measured engine settings),
the 36 existing benchmark unit tests, Python compilation and diff whitespace
checks. No resources were applied and no new GPU workload was run.
