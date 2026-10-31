See /home/mixa3607/k3s/kube/apps-ml/maya/values.yaml

Use docker.io/mixa3607/maya-gfx906:v1.1.45-rocm-10.1

See the [complete discussed flag inventory](../README.md) for classification,
current/default values, candidate values, decision statuses and fixed or best
tested values. Defaults are not measured optima. The first startup attempt was
[blocked by automatic TP4 to TP2 reduction](../results/baseline-spec1/README.md).
With `MAYA_DS4_TP_GGUF_UNEVEN=1`, the
[TP4 baseline benchmark completed](../results/baseline-spec1-tp4/README.md):
pooled prefill 369.11 tok/s and decode 31.24 tok/s with `spec=1`. Automatic CPU
selection used 74 threads; the 48/56-core candidates remain untested.

## Baseline settings

Keep the existing UD-Q8_K_XL pack, TP4, 524288-token context, 4096-token prefill
chunk and DSpark enabled. The baseline explicitly enables:

| Setting | Value | Purpose |
| --- | --- | --- |
| `MAYA_DS4_TP_GGUF_UNEVEN` | `1` | Permit whole-quant-block expert partitions so the requested TP4 is not reduced to TP2 by the ordinary path's 128-value FFN alignment rule. |
| `MAYA_DS4_PROMPT_SKIP` | `2` | DeepSeek's own approximate prompt skip: full work in layers 20-39 on the last 128 tokens, subject to the active path's chunk boundaries. This is intentionally not bit-exact. |
| `MAYA_DS4_SLOT_KEEP` | `1` | Save and restore conversations instead of rereading their entire prompts when requests switch. |
| `MAYA_DS4_SLOT_CAP` | `4` | Keep up to four parked conversations in RAM; further conversations spill to the slot directory. |

`MAYA_DS4_YOCO_TP=1` is only needed to allow the prompt skip on a single TP group
using `DS4_FLOW_TP=1`. The baseline does not enable that flow path, so neither
setting is added.

## Flag research scope

- Keep TP4. Exclude settings that require another TP width and Maya's
  non-bit-exact optimizations.
- Classify exactness using the documentation, not hypothetical engine bugs.
  `MAYA_DS4_MARKOV_Q8=1` is accepted as bit-exact at the verified-answer level:
  drafter outputs may change, but the documented verified answer does not. It
  remains a candidate and is not enabled in this baseline.
- The target host has two NUMA nodes with SMT disabled. Keep `DS4_COPY_NUMA=2`.
  CPU-thread candidates are 48 and 56 physical cores; a meaningful difference
  warrants extending the range in increments of eight cores. No explicit
  `--cpu-threads` value is selected yet.
- This directory records the baseline and flag constraints, not a step-by-step
  test plan. The linked benchmark is one baseline run, not evidence that each
  individual flag is optimal or that a 512K-token prompt has been tested.
