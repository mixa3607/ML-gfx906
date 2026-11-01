# DeepSeek V4.1 Flash: flag inventory

This is the inventory of flags discussed for the gfx906 optimization task, not
the complete Maya engine reference and not a step-by-step test plan.
The starting configuration is [base-params](base-params): Maya v1.1.45,
ROCm 10.1, the [v1.1.44 local patches](../build-context/patch/v1.1.44),
four MI50 GPUs and the existing UD-Q8_K_XL pack. The target CPU has two NUMA
nodes with SMT disabled.

## Reading the tables

| Status | Meaning |
| --- | --- |
| Always enabled | Kept unconditionally in the baseline, including fixed layout and model arguments. Not a claim of measured optimality. |
| Tested | Measured on this target in this task; the retained value and evidence are recorded. This is not a claim of a universal optimum. |
| Awaiting test | An accepted candidate; its current value is not a measured optimum. |
| Not used for now | Its tuning is excluded or inapplicable under the current constraints. This does not automatically turn off an existing upstream default. |

**Fixed / best tested value** contains only an unconditional baseline decision or
a measured, accepted value for the tested suite. `—` means neither has been
selected. Defaults and candidate values are separate columns: a default is not
a test result. An unset flag means it is not present in
`base-params/maya-config.json`; the displayed
default is documented upstream behavior, not a runtime observation.
Individually accepted best-tested flag values need not be enabled in the
current baseline. Their combined effect is untested unless explicitly measured;
individual speedups must not be added or multiplied as a measured prediction.

Classification follows the documentation and explicit task agreements;
hypothetical implementation bugs do not reclassify a flag. Bit-exactness refers
to the same target pack and the relevant computation path, not equality to the
original checkpoint or DeepSeek API. DSpark controls documented to preserve
verified answer tokens are accepted in group 1, including `MAYA_DS4_MARKOV_Q8`,
even if drafter internals change.
Documented changes to target arithmetic or prompt semantics are not bit-exact.

The rows within each optimization group retain the approximate ordering by
potential additional benefit on gfx906 in an applicable workload. TTFT, prefill
and decode gains are different metrics, so this is not a universal speed ranking.
The benchmark baseline fixes CPU48, TP4 and `spec=1`, with
`MAYA_DS4_SLOT_KEEP=0` to exclude conversation-slot save/load and disk spill.
Independent requests must report zero KV reuse. Native prompt timings still
include engine preparation and checkpoints; they are not pure GPU-kernel time.
The [selected CPU48 result](results/cpu-threads/README.md) records all 22 suite
requests completed, pooled prefill 347.64 tok/s and decode 35.67 tok/s over
the ten measurement requests. It measures the joint configuration, not flag optima.
The [CPU-thread comparison](results/cpu-threads/README.md) completed CPU56
and CPU48: pooled PP 347.03 / 347.64 tok/s and TG 35.72 / 35.67 tok/s,
respectively. Both improved TG versus CPU74 by about 18.7%; the difference
between 56 and 48 is below 0.2% on pooled PP/TG. CPU48 is selected by task
agreement, not as a proven winner over CPU56. No additional CPU count is selected.
The [five-arm CPU48 flag block](results/flags-cpu48/README.md) measured a fresh
control plus skip, swizzle, HC fuse and route fuse separately. By task agreement,
their individually best-tested values are `1`, `1`, `2` and `2`, respectively.
Per-length/per-request deltas and regressions remain recorded. The active
baseline is unchanged, and the combination has not been tested.

## Fixed baseline and inherited placement

These settings identify the workload and preserve the starting configuration.
Keeping them does not assert bit-exactness across alternative layouts. TP widths
other than 4 and Maya's non-bit-exact tuning are excluded.

| Flag | Current baseline | Other values discussed | Status | Fixed / best tested value | Role / decision |
| --- | --- | --- | --- | --- | --- |
| `--pack` | `/data/ds4` | Other quants are outside this task | Always enabled | `/data/ds4` (UD-Q8_K_XL) | Keep the original model pack and weight revisions. |
| `--gpus` | `0,1,2,3` | None | Always enabled | `0,1,2,3` | Four process-local GPU IDs. |
| `HIP_VISIBLE_DEVICES` | `1,0,3,2` | GPU permutations are excluded | Always enabled | `1,0,3,2` | Preserve the baseline device order. |
| `--tp` | `4` | `1`, `2`: excluded | Always enabled | `4` | No alternative tensor-parallel width. |
| `MAYA_DS4_TP_GGUF_UNEVEN` | Explicit `1` | No alternative selected | Always enabled | `1` | Whole-quant-block partitions preserve the requested TP4 instead of the ordinary path's automatic TP2 reduction; not a cross-layout bit-exactness claim. |
| `--max-context` | `524288` | Smaller contexts are not substitutes | Always enabled | `524288` | Keep the target context capacity. |
| `--prefill-chunk` | `4096` | `2048`, `8192`: excluded | Always enabled | `4096` | Changing chunk boundaries can change arithmetic; keep the baseline size. |
| `--mmap-experts` | `off` | No alternative selected | Always enabled | `off` | Preserve expert-copy mode; this alone does not guarantee every CPU expert is copied. |
| `--dspark` | `on` | No disablement selected | Always enabled | `on` | Drafting is already enabled; do not count its initial enablement as a new speedup. |
| `--vision` | `on` | No disablement selected | Always enabled | `on` | Preserve vision support. |
| `--expert-profile` | `/data/expert-profile.bin` | Profile refresh: excluded | Always enabled | `/data/expert-profile.bin` | Preserve the seed/profile path; the engine may update its counts. Alternative profiles can change CPU/GPU execution placement and output numerics. |
| `DS4_COPY_NUMA` | `2` | No alternative selected | Always enabled | `2` | Two NUMA parts on the actual two-node host. SMT is disabled. |
| `MAYA_DS4_DRAFT_DEV` | `1,2,3` | Lead-only and other placements: excluded | Always enabled | `1,2,3` | Preserve existing drafter placement. Changing it is not part of bit-exact tuning. |

## 1. Bit-exact / verified-answer-preserving candidates

The fusion patch admits gfx906 for `HC_FUSE`, `ROUTE_FUSE` and `DECODE_TRIM`
bits 1 and 2, preserving the upstream startup parity checks. The signed-zero
patch is a correctness fix, not a separate tunable speed switch.

| Flag | Current baseline / default | Candidate values | Status | Fixed / best tested value | Effect and limits |
| --- | --- | --- | --- | --- | --- |
| `MAYA_DS4_SLOT_KEEP` | Explicit `0` | No tuning requested | Not used for now | `0` | Disable conversation-slot save/load and spill so independent requests do not pay for preserving the preceding conversation. |
| `MAYA_DS4_SLOT_CAP` | Explicit `4`, inactive | No tuning requested | Not used for now | — | Ignored while `SLOT_KEEP=0`. |
| `DS4_SKIP_UNPICKED` | Unset; HIP default off | `0`, `1` | Tested | `1` | CPU48 at `1`: PP +15.12%, TG -0.79% versus fresh control. PP2048 +77.21%, PP32768 +3.51%; PP16384 TG -5.87%. Accepted individually by task agreement with this PP/TG tradeoff; baseline unchanged. Streams only experts picked by the chunk; unused by `DS4_FLOW_TP` or decode. |
| `DS4_ENGRAM_CACHE_MB` | Explicit `256` | `256`, `1024`, `4096`, `8192` | Awaiting test | — | More exact Engram row payloads cached in RAM; useful when Engram I/O is limiting. Competes with expert RAM and other host allocations. |
| `DS4_ENGRAM_RAM` | Unset; default `0` | None; `1` excluded | Not used for now | — | Lock both complete Engram tables, including scales. Excluded from testing on this host because there is insufficient RAM for the full tables alongside the existing workload. |
| `--cpu-threads` | Explicit `48` | `74`, `56`, `48` measured; extend by 8 cores only if the difference is meaningful and another run is approved | Tested | `48` (selected baseline) | CPU48: PP +3.91%, TG +18.61% versus CPU74. Selected by task agreement; no meaningful 56-vs-48 winner established. See the linked CPU-thread comparison. |
| `MAYA_DS4_CPU_LANE` | Unset; automatic policy bypassed by explicit CPU count | `cores`, `node`, `smt` were discussed; no separate policy tuning selected | Not used for now | — | CPU74/56/48 were measured with explicit thread counts. With SMT disabled, `smt` offers no extra logical siblings. Explicit counts bypass automatic thread-choice measurement. |
| `MAYA_DS4_HC_FUSE` | Unset; default `0` | `0`, `1`, `2`; `2` measured | Tested | `2` | CPU48 at `2`: PP +1.77%, TG +5.69% versus fresh control. Native single-/16-row parity checks passed on all four GPUs. Fuses HC split/norm and int8 rounding, including verify windows and shared-expert FFN input at `2`. Accepted individually by task agreement; baseline unchanged. |
| `MAYA_DS4_DECODE_TRIM` | Unset; default `0` | Individual bits `1`, `2`, `4`, `8`; combinations up to `15` | Awaiting test | — | `1`: shared-expert SwiGLU produces its int8 down input; `2`: q norm produces wq_b's int8 input; `4`: fuse snapshot/latent copies; `8`: mapped-host drafter handoffs. Local patch admits bits 1/2 on gfx906. |
| `MAYA_DS4_ROUTE_FUSE` | Unset; default `0` | `0`, `1`, `2`; `2` measured | Tested | `2` | CPU48 at `2`: PP +2.50%, TG +0.75% versus fresh control. Native single-/3-/16-row parity checks passed on all four GPUs. Router/lookahead in two launches, including verify windows at `2`; requires `DS4_AHEAD=1`. Accepted individually by task agreement; baseline unchanged. |
| `DS4_AHEAD` | Unset; default `1` | Keep `1` while evaluating route fusion | Always enabled | `1` (upstream default) | One layer of lookahead; dependency of `ROUTE_FUSE`, not an independent selected speed experiment. |
| `MAYA_DS4_HC_MIX_SPLIT` | Unset; default `0` | `0`, `1`; `2` was discussed for NVIDIA's side stream only | Awaiting test | — | Fuse HC mix/split on the layer's stream. On AMD the relevant comparison is `0` vs `1`; do not expect a distinct NVIDIA-side-stream benefit from `2`. |
| `DS4_HIP_ATTN_SWIZZLE` | Unset; opt-in | `0`, `1` | Tested | `1` | CPU48 at `1`: PP +3.80%, TG +0.81% versus fresh control. HIP attention LDS-layout optimization, accepted as bit-exact based on the user's reported prior tests; no new parity test here. Accepted individually by task agreement; baseline unchanged. |
| `MAYA_DS4_DRAFT_COST` | Unset; default `0` | `0`, `1` | Awaiting test | — | Choose verified window length from measured time/acceptance cost, preserving the answer. Alternative to the cumulative-confidence policy, not an independent multiplicative gain. |
| `MAYA_DS4_DSPARK_CUM` | Unset; default `0.5` | `0`, `0.25`, `0.5`, `0.75` | Awaiting test | — | Limit verification by cumulative draft confidence; relevant to the fixed-cut policy. The baseline already gets default `0.5`. |
| `--dspark-conf` | Unset; default `0.5` | `0.3`, `0.5`, `0.7` | Awaiting test | — | Per-draft confidence floor; balance accepted tokens against verification cost. |
| `DS4_DSPARK_LAZY` | Unset; default `1` | `0`, `1` | Awaiting test | — | Avoid drafter head/Markov work for rows the round cannot retain. Same drafts and answer tokens; already on by default, not an unconditional new enablement. |
| `MAYA_DS4_HEAD_COLS` | Unset; default `8` | `4`, `8`, `16` | Awaiting test | — | Output-head activations per pass. Same logits at every count; larger values help only when the call has enough rows. |
| `DS4_COPY_PIN` | Unset; default on with multiple GPUs, RAM copies and chunked prompts | `0`, `1` | Awaiting test | — | Copy prompt experts directly from pinned RAM without extra CPU staging. Setting/default alone does not prove pinning succeeded. |
| `DS4_REQUIRE_ALL_RAM` | Unset; default `0` | `0`, `1`, only with sufficient RAM | Awaiting test | — | With `--mmap-experts off`, require every CPU-lane expert in anonymous RAM or fail startup. A placement guarantee, not a gain if the baseline already copies them all; does not lock expert RAM. |
| `MAYA_DS4_MARKOV_Q8` | Unset; default `0` | `0`, `1` | Awaiting test | — | Halve the drafter Markov-head storage/traffic using Q8_0. Accepted as bit-exact at the verified-answer level by task agreement; drafter values and proposed tokens may change. |
| `MAYA_DS4_Q8_BATCH` | Unset; default `1` | `0`, `1` | Awaiting test | — | Batch int8 input-rounding jobs into one launch, same bits. Already enabled by default; no measured optimum selected. |
| `MAYA_DS4_Q8_SHARE` | Unset; default `1` | `0`, `1` | Awaiting test | — | Share identical rounded inputs across jobs, same bits. Already enabled by default; no measured optimum selected. |

`MAYA_DS4_SLOT_RAM_GB` and `MAYA_DS4_SLOT_DIR` are related slot configuration
controls, recorded because RAM budgeting and the slot directory were discussed:

| Flag | Current baseline / default | Candidate values | Status | Fixed / best tested value | Effect and limits |
| --- | --- | --- | --- | --- | --- |
| `MAYA_DS4_SLOT_RAM_GB` | Unset; inactive | No explicit RAM cap selected | Not used for now | — | Parked-state RAM budgeting is inactive while `SLOT_KEEP=0`. |
| `MAYA_DS4_SLOT_DIR` | Unset; inactive | No alternative path selected | Not used for now | — | Persistent slot storage is inactive while `SLOT_KEEP=0`. |

## 2. DeepSeek-designed non-bit-exact optimization

All applicable additional optimization switches in this category are enabled
immediately. There is one active candidate: `PROMPT_SKIP=2`. The TP-flow bridge
is conditional and does not require enabling another prompt path.

| Flag | Current baseline / default | Candidate values | Status | Fixed / best tested value | Effect and limits |
| --- | --- | --- | --- | --- | --- |
| `MAYA_DS4_PROMPT_SKIP` | Explicit `2` | `0`/`1` are reference modes, not selected alternatives | Always enabled | `2` | DeepSeek's approximate bounded replay: full layers 20-39 work on the last 128 prompt tokens. Answers can shift. TP4 off-flow can round the kept span to chunk boundaries, limiting the incremental gain over mode `1`. |
| `MAYA_DS4_YOCO_TP` | Unset; default off | `1` only if the single TP group uses `DS4_FLOW_TP=1` | Not used for now | — | Permit the prompt skip on a TP flow group. The baseline uses no TP flow; off-flow TP already supports the skip. |
| `DS4_FLOW_TP` | Unset; default off | No prompt-path change selected | Not used for now | — | TP experts use the streamed prompt flow. This is a path selector/dependency, not a new DeepSeek approximation; it is not needed to enable `PROMPT_SKIP=2` off-flow. |

Native DeepSeek FP8/FP4 rounding and packed attention caches are already part of
the engine/model path, not additional flags to enable. Their presence does not
imply hardware FP8/FP4 matrix acceleration on gfx906. DSpark is already enabled
and is not itself a non-bit-exact answer approximation.

## 3. Maya non-bit-exact tuning: excluded

Keep these rows for completeness, not as accepted experiments. Changes to TP,
chunk size, profile and drafter placement are recorded in the fixed-baseline
table rather than duplicated here. Exclusion of tuning does not retroactively
remove behavior already inherited from the starting configuration.

| Flag | Current baseline / default | Values discussed; not selected | Status | Fixed / best tested value | Effect / reason for exclusion |
| --- | --- | --- | --- | --- | --- |
| `--experts` | Unset; model default `6` | `6`, `5`, `4`, aggressive `3` | Not used for now | — | Fewer routed experts with renormalization. Changes the model; excluded even if expert compute/traffic falls substantially. |
| `MAYA_DS4_RAM_SKIP_W` | Unset; default `0` | `0`, `0.05`, `0.10`, `0.14` | Not used for now | — | Drop light routed experts absent from VRAM, including RAM-resident ones. Changes answers. Overrides the disk-skip mechanism when active. |
| `--threads` | Unset; TP4 already uses host threads | `on` for the rejected TP1 layout | Not used for now | — | No explicit override needed for the selected TP4 baseline. |
| `DS4_SPLIT` | Unset; automatic layer layout | Manual pipeline splits | Not used for now | — | Alternative layer/group layouts and summation paths were excluded. |
| `MAYA_DS4_DISK_SKIP_W` | Unset; default `0` | `0`, `0.05`, `0.10`, `0.14` | Not used for now | — | Drop light experts whose pages are not in RAM. Changes answers; no expected benefit if every CPU-lane expert is already in RAM. |
| `MAYA_DS4_DISK_SKIP_AUTO` | Unset; default `0` | `1` with disk skipping | Not used for now | — | Restrict approximate disk skipping to cold phases. Still changes answers while active. |
| `MAYA_DS4_DRAFT_VRAM` | Unset; automatic placement | Per-block expert-cache limits; no numeric grid selected | Not used for now | — | Rebalance drafter versus trunk cache room; changing CPU/GPU execution placement can change numerics. |
| `MAYA_DS4_DENSE_REQ` | Unset; default off | `q5_k`, then `q4_k` / `iq4_xs` | Not used for now | — | Additional dense-matrix requantization at load, not DeepSeek's native format. Changes target weights/answers. |
| `--suffix-draft` | Unset; default `3`, active | `0`, `3`, `4`, `6` | Not used for now | — | Prompt lookup can accelerate repeated code/text, but AMD long verify windows are documented not to give the same bits. Tuning is excluded; the inherited default has not been explicitly disabled. |
| `MAYA_DS4_KEEP_THINKING` | Unset; default off | `1` | Not used for now | — | Changes ordinary-chat prompt semantics by retaining earlier reasoning. Tool requests already retain it. |
| `MAYA_DS4_RESTORE_POINTS` | Unset; default `4`, active | No alternative count selected | Not used for now | — | Restore-point tuning is excluded: prompt segmentation and interaction with skip can change the first read's answer. The inherited default has not been explicitly disabled. |
| `MAYA_DS4_EXPERT_MMQ` | Unset; default off | `1` | Not used for now | — | Approximate IQ-expert prompt path with int8 activation/intermediate rounding; not a candidate for the current native-MXFP4 pack on gfx906. |
| `MAYA_DS4_PREFILL_FUSED` | Unset; not enabled by default on gfx906 | `1` on supported architectures/formats | Not used for now | — | Approximate fused WMMA prompt experts. RDNA/Strix speedups are not gfx906 evidence, and this is outside the accepted pack/path scope. |

## Other excluded or unclassified flags

| Flag | Current baseline / default | Values discussed; not selected | Status | Fixed / best tested value | Effect / reason for exclusion |
| --- | --- | --- | --- | --- | --- |
| `MAYA_DS4_HIP_PEER_AR` | Unset; default off | `auto`, `1` | Not used for now | — | Exact transport for eligible two-member HIP TP prompt groups only; not applicable to TP4. |
| `MAYA_DS4_AR2` | Unset; default `0` | `1` exact F32; `2` approximate FP16 on the wire | Not used for now | — | Two-member TP prompt all-reduce only. Both modes excluded under TP4; mode `2` also belongs to the rejected Maya approximations. |
| `MAYA_DS4_AR2_DECODE` | Unset; default `0` | `1` | Not used for now | — | Exact two-member TP decode all-reduce; not applicable to TP4. |
| `DS4_ENGRAM_PREFETCH` | Unset; default `0` | `1` | Not used for now | — | Exact Engram prompt read-ahead documented for one GPU; excluded from the four-GPU baseline. |

## Sources and evidence

- [Baseline JSON](base-params/maya-config.json) and
  [preparation script](base-params/prepare.sh).
- Maya v1.1.45
  [settings](https://github.com/mw00/project-maya/blob/v1.1.45/docs/SETTINGS.md),
  [models](https://github.com/mw00/project-maya/blob/v1.1.45/docs/MODELS.md) and
  [changelog](https://github.com/mw00/project-maya/blob/v1.1.45/CHANGELOG.md).
- [Skip-unpicked behavior and parity contract](https://github.com/mw00/project-maya/blob/v1.1.45/docs/ds4-skip-unpicked.md).
- [Exact HIP TP2 prompt transport](https://github.com/mw00/project-maya/blob/v1.1.45/docs/HIP_PEER_PREFILL.md).
- [Expert-profile placement and numerical caveats](https://github.com/mw00/project-maya/blob/v1.1.45/docs/DS4_PROFILE_REFRESH.md).
- [DeepSeek model configuration](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/blob/main/config.json):
  six routed experts per target token; native FP8/FP4 formats.

Local `git apply --check` accepted both v1.1.44 patches against upstream
v1.1.45. JSON/consistency/format checks are not GPU tests.
The [selected CPU48 baseline and CPU comparison](results/cpu-threads/README.md)
and [CPU74 reference](results/baseline/README.md) retain raw results, input and
artifact hashes, hardware metadata and rocBLASLt/Tensile diagnostics.
GPU runs and Kubernetes writes require separate explicit approval.
