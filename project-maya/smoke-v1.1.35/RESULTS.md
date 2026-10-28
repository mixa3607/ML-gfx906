# GLM-S24, MiniMax-XS and CYBER-FROST pass bounded gfx906 smoke checks

Date: 2026-10-28. All three models loaded on four MI50s and returned coherent
text through `/v1/chat/completions`. GLM and MiniMax also correctly described
the colored-shapes image and distinguished the blank control. These are short
functional checks, not a general quality evaluation or a benchmark.

## Configuration and image

- Four AMD Instinct MI50 32 GB / gfx906, node `kube-worker6.arkprojects.lan`.
- 76 visible CPU threads, 251 GiB host RAM; pod limit/request 220 GiB, no CPU
  quota. The runner raises its memlock limit before starting the servers.
- ROCm 10.1, upstream v1.1.35 at
  `e16dec85abf8801a4cfc086ee4814071a3ff54a2`, local v1.1.32 signed-zero patch.
- Test image:
  `registry.arkprojects.space/apps/maya-gfx906:v1.1.35-rocm-10.1-d21cdfc-pre`
  at `sha256:30ac6974fbe91c4fdc58e9b3b8093a9eddf22285bc2e31a24142ec20e1b687e5`.
- The private ROCm base tag was absent. The build used the published
  `docker.io/mixa3607/rocm-gfx906:10.1-complete` pinned to
  `sha256:b1d72163863a56b6b2bf498d159c1dc17627f8751aed6c8b8de2ebe9882972b4`;
  no ROCm version or architecture substitution.
- Remote build and runtime-library checks passed for `maya`, `maya-ds4`,
  `maya-mm3` and `maya-vision`. No DeepSeek model was loaded in this task.
- Model files were read from the `worker6-hf-cache` PVC, mounted read-only.
  The separately approved MiniMax companions download added about 4 GB to
  that cache. Model layouts used symlinks, not copied weight blobs.
- Runtime packs and configs were written into the test pod's `/data` emptyDir.
  All preparation scripts ran twice; the second invocation reused its pack.
- All configs used a 32768-token context capacity and four-GPU layer splits.
  Each HTTP request used temperature 0, seed 1, reasoning effort `none`, and a
  maximum of 384 output tokens. Prefix reuse was allowed, including the
  intentional conversation-continuation test. No throughput is scored.

Exact snapshots, parameters, image identity and effective final configs are in
the [guide](README.md), [pod manifest](pod.yaml), [provenance](provenance.json)
and [runtime record](runtime-final.json).

## Final functional results

| Model | Requests | Text | Image check | Drafting observed |
| --- | ---: | --- | --- | --- |
| GLM-5.3-Flash Maya-S24 | 7 | Pass | Red rectangle left, blue circle right; blank correctly identified | MTP accepted drafts |
| MiniMax-M3.1-Flash Maya-XS | 7 | Pass | Correct shapes and positions; blank described as off-white with no features | DSpark loaded on GPU3 and accepted drafts |
| Qwen-3.8-Flash-Next / CYBER-FROST | 5 | Pass | Not applicable: text only | MTP accepted drafts |

Each model returned `391` for `17 * 23`, gave two coherent Russian sentences
about freezing water, returned the correct Python list-comprehension function,
and recalled both the project name `Листопад` and code `48271` in a follow-up.
All 19 final HTTP responses finished naturally with `finish_reason: stop`,
not at the output limit. The generated function in every case was:

```python
def square_even(xs):
    return [x * x for x in xs if x % 2 == 0]
```

`/health` reported `status: ok`, images enabled for GLM/MiniMax and disabled
for CYBER-FROST. `/v1/models` reported the expected loaded models. Full HTTP
responses and engine/server/preparation logs are under
[`results/glm-s24`](results/glm-s24), [`results/minimax-xs`](results/minimax-xs)
and [`results/cyber-frost`](results/cyber-frost).

## Initial MiniMax launcher calibration: scope deviation and correction

The first MiniMax launch unexpectedly ran upstream's automatic prefill
calibration and DSpark speed comparison before opening the server. Omitting
`--calibrate` and setting the engine's `--no-prefill-tune` did **not** prevent
this: `maya.py` treats missing `installer.prefill_calibration` and
`installer.speed_calibration` as an old setup that needs measurement. It also
changed that first runtime config to DSpark **off**. This was outside the
requested no-benchmark scope; it is not relabeled as a functional check and no
performance conclusion is made from it. The initial logs and responses remain
under [`results/minimax-xs-initial-autocalibration`](results/minimax-xs-initial-autocalibration).

The final config explicitly records both calibrations as **skipped** and keeps
DSpark **on by choice**. The final seven-request MiniMax check was rerun with
that config; it started directly, loaded DSpark, and passed without another
launcher calibration. Its `--no-prefill-tune` also prevents reading the first
launch's saved tuning file. The smoke runner now checks upstream's calibration
predicates before starting a GPU engine and refuses a config that would
trigger either calibration. No upstream engine code was changed.

## Limits and cleanup

- No application/runtime errors were found in the final functional logs. All
  server wrappers exited with code 0; no engine processes remained afterward.
- The pod's final cgroup record reports `oom=0`, `oom_kill=0`, and no CPU
  throttling. Its memory peak nevertheless approached the 220 GiB limit and
  `memory.events max=2`: this serial run also retained charged file-cache
  pages from earlier models. It does not establish a safe lower RAM limit or
  memory requirements for separate production pods.
- Qwen logged limited host registration and unavailable huge pages, then
  successfully used its ordinary-page fallback. No huge-page or driver tuning
  was attempted.
- No full-32K input, long-context retrieval, tool-call, concurrent-serving,
  video, broad image-quality, sampled/thinking-output or parity test ran.
  Native log/HTTP timing fields are retained as evidence, not a benchmark.
- The temporary pod was deleted. All four GPUs returned to 0% usage and
  10 MiB allocated per GPU; see [GPU cleanup](gpu-after-cleanup.txt).
- The existing Helm release remains scaled to zero and its configuration/PVC
  were not modified. Unrelated workloads remain running; see
  [post-cleanup inventory](pods-after-cleanup.txt). Only downloaded companions
  remain in the cache; the temporary generated packs were removed with the pod.
