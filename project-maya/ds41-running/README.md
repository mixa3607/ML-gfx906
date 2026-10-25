# DeepSeek-V4.1 on four MI50s

Each YAML contains its own ConfigMap, data PVC and Deployment with model
preparation for `kube-worker6.arkprojects.lan`.

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
off. There is no CPU quota. Each setup stores its data separately on
`maya-ds41-prefill-data` or `maya-ds41-decode-data`; model blobs remain in the
read-only `worker6-hf-cache` PVC. Both use the existing `apps-ml` namespace,
`local-path` storage class and `harbor-registry-pull-secret`. No Service is created.

For decode, retained peer-pod memory must stay below 1Gi to keep the combined
budget within 200Gi. First-time vision preparation uses small HTTP Range
requests for marker rows; model shards are not downloaded.
