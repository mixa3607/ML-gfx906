# DeepSeek-V4.1 on four MI50s

Each YAML contains its own ConfigMap, data PVC and Deployment with model
preparation for `kube-worker6.arkprojects.lan`.

## Results

| File                           | Profile                           | PP2K / PP4K / PP8K, tok/s | TG, tok/s | Container RAM cap |
| ------------------------------ | --------------------------------- | ------------------------- | --------: | ----------------- |
| [`prefill.yaml`](prefill.yaml) | TP2, whole-block flow, pump1      | 106.61 / 133.62 / 182.65  |    21.866 | 200Gi             |
| [`decode.yaml`](decode.yaml)   | Genuine TP4, whole-block, no flow | 87.66 / 139.42 / 147.68   |    27.492 | 200Gi             |
| [`dspark.yaml`](dspark.yaml)   | TP4, DSpark default, chunk2048 ([3 warmups / 3 scored](../ds41-running-spec-tmp/coarse-2048-tg256/RESULTS.md)) | 92.20 / — / — | 38.173 | 220Gi |

Measurements use six serial TG256 non-thinking requests after 12 warmups, with
no KV reuse or logit dumps. The profiles were measured in separate runs, not a
direct comparison; see [RESULTS.md](../ds41-running-tmp/RESULTS.md), approaches 5–6.
