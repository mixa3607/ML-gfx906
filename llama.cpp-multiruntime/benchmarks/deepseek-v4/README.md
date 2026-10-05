# DeepSeek V4 Flash: ROCm + CUDA placement

## Environment

- Model: `orcarouter/DeepSeek-V4-Flash-Vision-Uncensored-GGUF`, MXFP4, four shards.
- GPUs: 4 x 32 GiB gfx906, 2 x 16 GiB RTX 5060 Ti (sm120).
- Binary: llama.cpp 0.5.0-dev, build 1, commit `7fe450e`.
- Test pod: `apps-ml/llama-server-multi-llamacpp-6b5594cd69-8tjxc`.
- Image digest and relevant environment variables: `environment.json`.
- Stock profile captured from the AMD router's `/models`: `stock-preset.ini`.
- Model revision: `e262f88e8b1fdd390a2c0cad2af436dce4c8fa0e`.

## Results

Three repetitions, medians, tokens/s; 128 generated tokens per request.
Per-run ranges are saved in `*-summary.json`.

| Placement | ubatch | PP512 | TG after 512 | PP2048 | TG after 2048 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stock ROCm + CPU | 2048 | 90.37 | 10.05 | 168.87 | 10.01 |
| Twelve CPU expert pairs to CUDA | 2048 | 121.21 | 12.12 | 184.05 | 11.62 |
| Router projection only to CUDA | 2048 | 88.68 | 10.08 | 157.45 | 9.76 |
| Stock ROCm + CPU, smaller ubatch | 512 | 91.36 | 10.80 | 85.81 | 10.59 |
| Layers/KV on CUDA, experts ROCm/CPU | 2048 | 109.96 | 12.61 | 200.68 | 12.13 |
| All experts on six GPUs, headroom adjustments | 512 | **198.27** | **20.37** | **221.15** | **20.51** |
| Dense on CUDA, 16 CPU pairs to ROCm | 2048 | 176.71 | 20.15 | 291.52 | 19.35 |
| Same, 64 CPU threads | 2048 | 167.45 | 17.10 | 272.86 | 17.06 |
| Same, 64 threads and `--numa isolate` | 2048 | 152.56 | 4.09 | 277.97 | 4.08 |

CPU-side tuning does not help this placement. Doubling `--threads` to 64 costs
15% of generation speed, and `--numa isolate` collapses generation to 4.1
tokens/s. The stock 32 threads stay.

## Expert tensor priority

Routed `up`, `gate`, and `down` expert tensors are all 1088 MiB and all used by
the same 6 selected experts per token, and llama.cpp's DeepSeek V4 path runs
separate matmuls for each (the fused `gate_up_exps` path exists only for
architectures that store a combined tensor). Preferring one of the three by
type therefore gives nothing: `ffn_gate_exps` is an expert projection, not the
router. What matters is keeping each layer's expert set together on one device
and minimizing the number of CPU-resident layers. The router itself
(`ffn_gate_inp`, 2 MiB BF16 per layer) is already always on a GPU; moving it to
CUDA alone produced no gain.

## DSpark speculative decoding

This llama.cpp build supports `--spec-type draft-dspark` (arch `dflash`), and
prebuilt drafters exist for DeepSeek-V4-Flash. The tested file is
`alessandrobologna/DeepSeek-V4-Flash-DSpark-Drafter-GGUF`, variant
`...-Q2_K-Q8_0-dflash.gguf` (6.98 GB, arch `dflash`, block size 5, target
layers 41-43). Variant generation: `make-dspark-variant.py`; it removes the
stock draft arguments and appends the DSpark ones.

Key runtime requirement: the draft shares the target's `output.weight`, so the
draft device list must include the device holding it (CUDA1 here). With
`--spec-draft-device none` the server aborts during draft context creation
(`pre-allocated tensor (output.weight) in a buffer (CUDA1) that cannot run the
operation`). Draft weights stay on CPU with `--spec-draft-ngl 0`.

| Draft device | PP512 | TG512 | PP2048 | TG2048 | CUDA free after (MiB) |
| --- | ---: | ---: | ---: | ---: | --- |
| (no draft, constrained winner) | 176.71 | 20.15 | 291.52 | 19.35 | 8186 / 7723 |
| CUDA1 | 148.57 | 22.24 | 281.35 | 21.62 | 8240 / 5401 |
| CUDA0,CUDA1 | 166.61 | 21.02 | 267.98 | 20.64 | 7032 / 5559 |

Output hashes are identical to the baseline in the synthetic runs. The draft
graph consumes ~2.2-2.3 GiB of device buffers; under the 6.5 GiB free
constraint neither tested device layout fits on CUDA1 (total CUDA slack is only
2597 MiB while allocation lands mostly on one card). Fitting it would need
either a rebalance of ~1 GiB of main-model layers from CUDA1 to CUDA0 or
~1.1 GiB of relaxed headroom on that card.

Realistic-prompt A/B (483-token Russian instruction, 256 generated, 2
repetitions, medians):

| Config | PP tokens/s | TG tokens/s | Draft accepted |
| --- | ---: | ---: | ---: |
| No draft | 155.53 | 18.78 | - |
| DSpark, draft on CUDA1 | 147.01 | 15.40 | 175/319 (55%) |

Speculation makes generation 18% slower on real content. The drafter is
matched to DeepSeek-V4-Flash-0731 while the served model is a Vision-Exp
abliterated finetune, so only 55% of draft tokens are accepted; the synthetic
repeated-text prompt accepted 100% and is not representative. On top of that,
the MoE verify forward reads all experts for every candidate token, so each
verified token costs close to a full decode step and speculation only pays off
at very high acceptance. The realistic runs also produce different output
hashes between the two configs: batched verification is not bit-for-bit
identical to single-token decoding, so greedy outputs can diverge on near-ties.

Verdict: DSpark with a CPU-resident mismatched drafter is not a win for this
model under the 6.5 GiB CUDA headroom constraint. A drafter trained for this
exact finetune and a GPU-resident draft could raise acceptance and cut
overhead, but a GPU-resident draft needs about 2.3 GiB more CUDA headroom than
the constraint allows.

Best measured placement: `all-gpu-headroom.json`, with a deployable candidate in
[`profiles/deepseek-v4-flash-6gpu.yaml`](profiles/deepseek-v4-flash-6gpu.yaml).
The best constrained placement (CUDA free >= 6.5 GiB) is
`dense-cuda-redistributed-plus.json`, candidate profile in
[`profiles/deepseek-v4-flash-constrained.yaml`](profiles/deepseek-v4-flash-constrained.yaml).
TG improves **2.03x / 2.05x** over original stock and **1.89x / 1.94x** over
the stock-ubatch-512 control. All six output hashes match stock in every
successful placement. The candidate has not been deployed to the production router.

The winner assigns four initial blocks to each CUDA GPU, then 9/9/9/8 blocks
and the output head across ROCm0-3. It keeps the token embedding on CPU
(1010 MiB) but all expert weights on GPU. Flash Attention remains enabled.
The explicit output override disables pipeline parallelism; mmproj is on ROCm3.
Server ready in 40.1 seconds (loading times were not controlled cold-cache tests).
After requests, NVIDIA memory use is 14659 / 14748 MiB; AMD use in ROCm order is
31.847 / 31.665 / 31.847 / 30.289 GiB. ROCm0/2 have only about 140 MiB free.
This profile passed the stated short text workload; long occupied contexts,
image inputs, and concurrent requests still need separate validation.

The constrained winner keeps layers/KV on CUDA (split 22:22:0:0:0:0), all 16
expert pairs of layers 0-3 / 11-14 / 22-25 / 33-36 on ROCm, and the
remaining 7 pairs (14.9 GiB) on CPU. Its prompt speed is 176.71 / 291.52 and
generation 20.15 / 19.35; output hashes match stock. After requests, NVIDIA
memory use is 8125 / 8588 MiB (8186 / 7723 MiB free), and only about 0.43-0.51
GiB remains free on each ROCm device. The candidate profile keeps the override
table grouped by target with one list item per layer; layers 4, 5, 15, 16, 26,
27, 37 contribute only a gate item to their ROCm group, with up/down listed
under CPU. It is placement-equivalent to the measured command and contains no
overlapping patterns.

### 192k end-to-end verification

The constrained profile was verified through the full image path: profile YAML
-> `server-profiles/build-presets-ini.py` -> `LLAMA_ARG_MODELS_PRESET` ->
router -> autoload -> completions (`e2e-192k.py`), with ctx-size patched to
196608. The router loaded the model by the first request in 47.1 s and reported
the exact profile arguments. KV buffers scale by 1.5: main 1280 -> 1920 /
1408 -> 2112 MiB, indexer 320 -> 480 / 352 -> 528 MiB, HCA 40 -> 60 MiB; the
SWA part stays at 198 / 189 MiB. After a 23400-token prompt and generation,
CUDA free is 7482 / 6931 MiB: 826 / 275 MiB above the 6.5 GiB floor, and
1283 / 732 MiB above a decimal 6.5 GB floor. Memory stays flat afterwards.
Raw data: `raw/e2e-192k-run`.

To render the candidate through the existing profile builder, from this directory:

```bash
python3 ../../../llama.cpp/build-context/extra/server-profiles/build-presets-ini.py \
  --source-dir profiles --output /tmp/opencode/deepseek-v4-6gpu.ini
```

CUDA expert offload improves TG by 20.7% / 16.1%. Its CUDA weight buffers are
13056 MiB each, compute buffers 514 MiB each; observed NVIDIA VRAM after requests
is 13887 / 13754 MiB. Host weights decrease from 51058 to 24946 MiB.

Router-only placement gives no meaningful generation gain. Assigning layers/KV
to CUDA while retaining expert placement on ROCm/CPU improves TG by 25.5% / 21.2%
vs. stock. Reducing ubatch alone improves TG in these runs but almost halves
PP2048 throughput; it must not be confused with a CUDA-placement gain.

The first dense-weight override experiment fails at context initialization.
`resolve_fused_ops` detects CUDA attention on a ROCm-assigned layer and disables
Flash Attention and fused HC operations. Reserving an 18372 MiB ROCm0 compute
buffer then fails with OOM. This run has no throughput result.
`dense-cuda-aligned.json` instead assigns layers and KV to CUDA, keeping CPU
expert overrides first and overriding the remaining experts to ROCm.

The first all-GPU run loads in 38.1 seconds, then fails at the first request with
`cublasCreate_v2: the resource allocation failed`. CUDA0 already uses 15791 MiB;
ROCm0/2 use 31.96 GiB each. With no tensor overrides, llama.cpp enables pipeline
parallelism and allocates additional buffers. `all-gpu-headroom.json` explicitly
pins the output weight to its existing ROCm3 device (disabling pipeline
parallelism) and moves the projector from CUDA0 to ROCm3.

Stock server ready in 98.3 seconds. Four auto-configured slots, unified 131072
token context pool; only slot 0 receives requests. ROCm weight buffers:
24563 / 24571 / 24591 / 24346 MiB; host weights 51058 MiB (includes embedding).
AMD VRAM after the requests: approximately 28.52 / 27.04 / 27.09 / 26.80 GiB in
ROCm device order. All three output hashes match at each prompt length.

The synthetic prompt produces a continuation of the repeated records. It is
useful for controlled placement comparisons; confirm promising placements on
representative chat/code workloads before interpreting them as general gains.

## Context growth

`context-growth.py` fills one slot to 126976 tokens on the constrained placement
and samples memory after every step. CUDA memory stabilizes ~170 MiB below the
post-load value after the first inference (allocator/graph workspaces) and then
does not move: 8304/8025 MiB free at 2048 fill, 8302/8023 MiB free at 126976
fill. ROCm free memory is constant at 0.53/0.45/0.45/0.45 GiB. The KV, state,
and compute buffers are preallocated for the configured context, so context fill
adds no VRAM consumption in this runtime.

| Fill (tokens) | PP tokens/s | CUDA free (MiB) | RSS (GiB) |
| ---: | ---: | ---: | ---: |
| 2048 | 273.9 | 8304 / 8025 | 18.15 |
| 8192 | 283.0 | 8302 / 8023 | 18.20 |
| 32768 | 243.5 | 8302 / 8023 | 18.25 |
| 65536 | 244.6 | 8302 / 8023 | 18.29 |
| 98304 | 230.9 | 8302 / 8023 | 18.34 |
| 126976 | 219.3 | 8302 / 8023 | 18.38 |

Host RSS grows by 0.70 GiB over the whole fill (prompt cache and context
checkpoints, bounded by `cache-ram 32768`); `MemAvailable` stays flat. Prompt
processing keeps 216-283 tokens/s even at 127k depth. A 128-token generation at
126993 fill runs at 17.11 tokens/s (58.43 ms/token) versus 19.35-20.15 tokens/s
at 512-2048 fill: roughly 12-15% slower at maximum depth. Short 8-token
generations show lower averages because the first token after prompt processing
dominates them; both measurements are in `raw/context-growth-plus-run-5`.

## Method

`baseline.json` contains the active stock command with only the HTTP port changed
to 18080. This preserves the 131072 context setting, auto slot count, mmproj,
32 CPU threads, batch/ubatch 2048, mlock, and disabled speculation.

`run.py` starts a standalone server, waits for health, performs a 128-token / 16
generation warmup, then measures single-request concurrency with 512 and 2048
input tokens, 128 output tokens, three repetitions each. Prompts are tokenized
once, truncated to exact lengths, and saved. Requests use greedy sampling,
seed 42, `ignore_eos=true`, `cache_prompt=false`, and slot 0. The runner checks
that server timings account for the entire prompt and all requested output.

PP and TG are reported separately from the server's timing fields. Wall time
is also saved; it includes scheduling and HTTP overhead. These are text-only
short-context tests with the stock context *capacity*, not benchmarks at 128K
occupied context or vision workloads. Saved output text/hashes permit checking
obvious output differences but are not a model-quality evaluation.

Each run saves the command, `/props`, full server log, warmup, raw responses,
hardware snapshots, JSONL measurements, and median/min/max summary. The runner
terminates its own server in `finally`. Run one placement at a time on idle GPUs.

```bash
python3 make-variants.py
# Copy run.py and the desired command JSON into the test pod, then:
python3 run.py baseline.json baseline-run
python3 run.py cpu-experts-to-cuda.json cpu-experts-to-cuda-run
```

`context-growth.py` fills one slot in steps (`2048, 8192, ..., 126976` tokens) with
`cache_prompt=true` and records NVIDIA, AMD, and host memory after every step.
It fails the run if prompt accounting is impossible, and flags a full
reprocessing if the server dropped the cached prefix.

## Placement experiments

The initial override-only experiments append CUDA devices to `--device` with
zero tensor-split weights, keeping automatic layer placement on ROCm. Their
CUDA overrides precede the stock CPU overrides because the loader uses the
first matching expression. The aligned dense experiment reverses this: layers
are assigned to CUDA; CPU overrides precede general expert-to-ROCm overrides.

| Command | Change from stock |
| --- | --- |
| `baseline.json` | ROCm + CPU, no CUDA weights |
| `cpu-experts-to-cuda.json` | CPU up/down experts in layers 0-5 to CUDA0, 11-16 to CUDA1; 12.75 GiB weights per CUDA GPU |
| `router-to-cuda.json` | Only `ffn_gate_inp` to CUDA, split at layer 21; roughly 86 MiB total |
| `dense-to-cuda.json` | Non-expert block weights and output head to CUDA; stock CPU expert overrides retained |
| `baseline-ub512.json` | Stock placement with ubatch 512, control for the following experiment |
| `all-gpu-ub512.json` | No CPU expert overrides; CUDA0/CUDA1 first, ROCm0-3 next, split 4:4:9:9:9:9, ubatch 512 to reduce compute buffers |
| `all-gpu-headroom.json` | Same weight split, explicit output override disables pipeline parallelism, mmproj on ROCm3 |
| `dense-cuda-aligned.json` | CUDA layer/KV placement, split 22:22:0:0:0:0; original CPU expert overrides, remaining expert weights explicitly on ROCm0-3 |
| `dense-cuda-redistributed.json` | Same, plus expert pairs of layers 0-2/11-13/22-24/33-35 moved from CPU to ROCm; mmproj on ROCm3 |
| `dense-cuda-redistributed-plus.json` | Additionally layers 3/14/25/36 pairs on ROCm; 7 pairs (14.9 GiB) remain on CPU |

The supplied GGUF inspection lists 145.64 GiB of files, including 137.06 GiB
expert weights. Each up/gate/down expert tensor is 1088 MiB. The stock profile
places up/down expert tensors from **23 layers** on CPU (48.875 GiB): 0-5,
11-16, 22-27, 33-37. Moving twelve pairs to CUDA removes 25.5 GiB from that set.
Actual allocated VRAM also includes KV, compute buffers, and the projector.

`ffn_gate_inp` is the router projection; `ffn_gate_exps` is the experts' gated
projection, not routing. Moving only the router adds backend boundaries while
leaving the large CPU expert workload intact. CUDA/ROCm transfers fall back to
host staging in the generic backend copy path; minimizing such boundaries may
matter more than the router's compute speed. Dense-weight overrides alone do
not explicitly relocate the KV cache.

Source references in the local llama.cpp checkout:

- `src/models/deepseek4.cpp`: `build_moe_ffn`, router vs. expert inputs.
- `src/llama-model-loader.cpp`: first matching tensor-buffer override wins.
- `src/llama-context.cpp`: pipeline parallelism is disabled with tensor overrides.
- `ggml/src/ggml-backend.cpp`: `ggml_backend_tensor_copy`, host-staged fallback.
- `ggml/src/ggml-cuda/ggml-cuda.cu`: buffer/backend checks in copy functions.

Raw run directories are stored under ignored `raw/` when copied back from the pod.
