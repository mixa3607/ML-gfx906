See /home/mixa3607/k3s/kube/apps-ml/maya/values.yaml

Use docker.io/mixa3607/maya-gfx906:v1.1.45-rocm-10.1

See the [complete discussed flag inventory](../README.md) for classification,
current/default values, candidate values, decision statuses and fixed or best
tested values. Defaults are not measured optima.

The [selected CPU48 baseline result](../results/cpu-threads/README.md) records
pooled prefill 347.64 tok/s and decode 35.67 tok/s on `ds41f-ru-long`, with
TP4, `spec=1`, disabled conversation slots and no KV reuse. CPU48 is selected
by task agreement: +3.91% PP and +18.61% TG versus the CPU74 reference.
CPU56 and CPU48 differ by less than 0.2% in pooled PP/TG; this selection is
not a claim that CPU48 is a unique or universal optimum.

## Baseline settings

Keep the existing UD-Q8_K_XL pack, TP4, 524288-token context, 4096-token prefill
chunk and DSpark enabled. Requests use `temperature=0 spec=1`, without
cross-request KV reuse. Conversation slots are disabled so prompt timings do
not include saving/spilling the preceding conversation. Native prompt timings
still include engine state preparation and checkpoints, not just GPU kernels.

The baseline explicitly sets:

| Setting | Value | Purpose |
| --- | --- | --- |
| `MAYA_DS4_TP_GGUF_UNEVEN` | `1` | Permit whole-quant-block expert partitions so the requested TP4 is not reduced to TP2 by the ordinary path's 128-value FFN alignment rule. |
| `--cpu-threads` | `48` | Selected CPU48 baseline; pin the CPU lane instead of rerunning automatic thread selection. |
| `MAYA_DS4_PROMPT_SKIP` | `2` | DeepSeek's own approximate prompt skip: full work in layers 20-39 on the last 128 tokens, subject to the active path's chunk boundaries. This is intentionally not bit-exact. |
| `MAYA_DS4_SLOT_KEEP` | `0` | Disable conversation-slot save/load and disk spill for independent benchmark requests. |
| `MAYA_DS4_SLOT_CAP` | `4` | Inactive while `SLOT_KEEP=0`. |

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
  CPU-thread candidates 48 and 56 were measured; 48 is the selected baseline.
  A meaningful difference can warrant
  extending the range in increments of eight cores, with another run approval.
  No additional CPU-thread runs are selected.
- This directory records the baseline and flag constraints, not a step-by-step
  test plan. The benchmark suite measures prompts up to 32768 tokens, not the
  full configured 512K-token context capacity.
