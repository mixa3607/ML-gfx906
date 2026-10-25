# DeepSeek-V4.1 on four MI50s

Each YAML contains a ConfigMap, data PVC, Deployment with model preparation,
and Service for `kube-worker6.arkprojects.lan`.

## Results

| File | Profile | PP2K / PP4K / PP8K, tok/s | Aggregate PP, tok/s | TG, tok/s | Scored wall, s | Container RAM cap |
| --- | --- | --- | ---: | ---: | ---: | --- |
| [`prefill.yaml`](prefill.yaml) | TP2, whole-block flow, pump1 | 106.61 / 133.62 / 182.65 | **151.36** | 21.866 | 259.420 | 187Gi |
| [`decode.yaml`](decode.yaml) | Genuine TP4, whole-block, no flow | 87.66 / 139.42 / 147.68 | 132.48 | **27.492** | 272.093 | 199Gi |

Measurements use six serial TG256 non-thinking requests after 12 warmups, with
no KV reuse or logit dumps. The profiles were measured in separate runs, not a
direct comparison; see [RESULTS.md](../ds41-running-tmp/RESULTS.md), approaches 5–6.

- Prefill: best measured aggregate PP on 2K–8K; passed 64K retrieval and vision,
  but its diagnostic 64K prefill was slower than stock TP2 (393s versus 271s).
- Decode: TG +25% against its matched TP2 control, but total request time +1%.
  TP4 passed the short numerical checks; **64K/vision were not tested**.
  Loads at 187Gi and 190Gi OOMKilled; keep the 199Gi cap.

Stock TP2 without flow remains the full-range default. Holdout was not run;
these manifests have client/CPU validation only, not deployment testing.

## Configuration

Image: `docker.io/mixa3607/maya-gfx906:v1.1.27-rocm-10.1`.
Model: `unsloth/DeepSeek-V4.1-Flash-1017-GGUF:UD-Q8_K_XL`.
Model and vision snapshot revisions are set in `prepare.sh` inside each YAML.

Both profiles use CPU56, NUMA2 full RAM copies, chunk4096, Engram256MiB,
ring400MiB, context196608 and native vision. YOCO, expert skips and DSpark are
off. There is no CPU quota. Preparation and learned expert profiles persist
on `maya-ds41-data`; model blobs remain in the read-only HF cache.

## Run

Requires the existing `apps-ml` namespace, `local-path` storage class,
`worker6-hf-cache` PVC with the model and vision inputs, and
`harbor-registry-pull-secret`. First-time vision preparation reads about 30KB
of marker rows plus the shard header via HTTP Range; no whole shards are downloaded.

Ensure all four GPUs are free. For decode, other retained test-pod memory must
stay below 1Gi to keep the combined usage within 200Gi; Kubernetes only enforces
the individual container cap.

**Apply one file, not the directory.** Both files use the same resources;
`Recreate` replaces the current server when switching profiles.

```bash
kubectl apply -f prefill.yaml
# Or:
# kubectl apply -f decode.yaml
kubectl -n apps-ml rollout status deployment/maya-ds41 --timeout=2400s
kubectl -n apps-ml logs deployment/maya-ds41 -c prepare
kubectl -n apps-ml logs deployment/maya-ds41 -c maya
kubectl -n apps-ml port-forward service/maya-ds41 8080:8080
```

API: `http://127.0.0.1:8080/v1`, model `deepseek-v4.1-flash`. The ClusterIP
Service has no API key; add authentication before external exposure.
Engine logs are `/data/prefill.log` and `/data/decode.log`. Restart the Deployment
after ConfigMap-only edits. See [RUNNING.md](../RUNNING.md) for API/image usage.

Stop without deleting the prepared data:

```bash
kubectl -n apps-ml scale deployment/maya-ds41 --replicas=0
```

`kubectl delete -f` also deletes the application PVC.

## Validation

Requires PyYAML and `kubectl`:

```bash
python3 -m unittest discover -s . -p 'test_*.py'
kubectl create --dry-run=client -f prefill.yaml -o name
kubectl create --dry-run=client -f decode.yaml -o name
```
