See /home/mixa3607/k3s/kube/apps-ml/maya/values.yaml

Use docker.io/mixa3607/maya-gfx906:v1.1.45-rocm-10.1

See the [complete discussed flag inventory](../README.md) for classification,
current/default values, candidate values, decision statuses and fixed or best
tested values. Defaults are not measured optima.

## Final selected baseline

By final task agreement, [maya-config.json](maya-config.json) selects **CPU48
plus four flags**: `DS4_SKIP_UNPICKED=1`, `DS4_HIP_ATTN_SWIZZLE=1`,
`MAYA_DS4_HC_FUSE=2` and `MAYA_DS4_ROUTE_FUSE=2`. It exactly matches the
measured [all-four configuration](../results/combos-cpu48/all/maya-config.json).
On `ds41f-ru-long`, pooled prefill is **410.83 tok/s** and decode **35.88 tok/s**:
+19.19% PP and +2.34% TG versus the saved CPU48 control (344.69/35.06).
This is the selected combined result, not the sum of individual gains or a
universal optimum; HC alone had higher pooled TG. The suite covers prompts
through 32768 tokens, not the full configured 512K context.

Keep Engram cache `256` and unset/default-off Markov Q8, draft cost, decode
trim and HC mix/split. The [six-/seven-flag comparison](../results/final-candidates-cpu48/README.md)
did not improve both pooled rates over four flags; draft cost/trim's earlier
individual selection is superseded by this final combined choice. Old
references are not contemporaneous controls, so this is not proof that a
particular extra flag is always harmful. No further main-campaign runs are selected.

The separately approved [layout/chunk side story](../results/side-layout-cpu48/README.md)
tests TP2 and, independently, prefill chunk 2048 from this configuration. It
does not modify this final baseline and does not assume cross-layout bit-exact
answers.
The two side runs completed at pooled PP/TG 248.78/25.79 tok/s for TP2 and
352.54/35.08 for chunk2048, both below this baseline's saved 410.83/35.88.
No fresh control or answer-parity test was run; this baseline remains unchanged.

The [CPU-thread comparison](../results/cpu-threads/README.md),
[individual flags](../results/flags-cpu48/README.md),
[combinations](../results/combos-cpu48/README.md) and
[top-five block](../results/top5-cpu48/README.md) retain the research history.
This change updates the repository baseline only: no deployment, new GPU run,
image build or publication is performed.

CPU-only validation of the final selection passed: 66 tests across the
benchmark runner and five result-analysis suites, including exact equality
with the measured all-four config. Archived flag-result launchers still guard
against changing their original control baseline and will refuse this new
active config; they are not entry points for a new campaign without a new
approved plan. CPU-only analysis uses the captured historical inputs.

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
| `DS4_SKIP_UNPICKED` | `1` | Stream only prompt experts picked by the chunk. |
| `DS4_HIP_ATTN_SWIZZLE` | `1` | Enable the selected HIP attention LDS layout. |
| `MAYA_DS4_HC_FUSE` | `2` | Enable HC fusion, including verify windows and shared-expert FFN input. |
| `MAYA_DS4_ROUTE_FUSE` | `2` | Enable route fusion, including verify windows; retain default `DS4_AHEAD=1`. |
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
  is not selected for the final baseline.
- The target host has two NUMA nodes with SMT disabled. Keep `DS4_COPY_NUMA=2`.
  CPU-thread candidates 48 and 56 were measured; 48 is the selected baseline.
  A meaningful difference can warrant
  extending the range in increments of eight cores, with another run approval.
  No additional CPU-thread runs are selected.
- This directory records the baseline and flag constraints, not a step-by-step
  test plan. The benchmark suite measures prompts up to 32768 tokens, not the
  full configured 512K-token context capacity.
