# Maya v1.1.35 functional checks on gfx906

These are functional checks, not benchmarks or a speed calibration. Use one
model at a time on four MI50 32 GB cards, with 220 GiB of pod RAM and no CPU
quota. The example configs use a 32K context; short smoke requests do not
validate the full context or general model quality.

Completed checks and limitations, including the initial MiniMax automatic
calibration incident, are recorded in [RESULTS.md](RESULTS.md).

| Model | Config and offline preparation | Images | Drafting |
| --- | --- | --- | --- |
| GLM-5.3-Flash Maya-S24 | [config](../glm-s24/maya-config.json), [prepare.sh](../glm-s24/prepare.sh) | CPU helper | Model's MTP with the layer split |
| MiniMax-M3.1-Flash Maya-XS | [config](../minimax-xs/maya-config.json), [prepare.sh](../minimax-xs/prepare.sh) | Native tower | DSpark, no speed calibration |
| Qwen-3.8-Flash-Next / CYBER-FROST | [config](../cyber-frost/maya-config.json), [prepare.sh](../cyber-frost/prepare.sh) | Text only | MTP built from its GGUF |

## Downloads

Run these outside the serving pod, with `HF_HOME` on the intended cache PVC.
They pin the files used by the preparation scripts. Do not download the whole
MiniMax EXL3 repository: only its separate vision/DSpark files are needed.

```bash
hf download peasantsmith/GLM-5.3-Flash-Maya-GGUF \
  'Maya-S24/GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00001-of-00003.gguf' \
  'Maya-S24/GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00002-of-00003.gguf' \
  'Maya-S24/GLM-5.3-Flash-Maya-S24-IQ2_XXS_S-00003-of-00003.gguf' \
  vision/mmproj-GLM-5.3-Flash-F16.gguf vision/GLM-5.3-Flash-vocab.gguf \
  --revision f16ee4ba50d8fd2bb726ea1862ca6ca14ba188da

hf download peasantsmith/MiniMax-M3.1-Flash-Maya-GGUF \
  Maya-XS/MiniMax-M3.1-Flash-Maya-XS-IQ1_S-00001-of-00002.gguf \
  Maya-XS/MiniMax-M3.1-Flash-Maya-XS-IQ1_S-00002-of-00002.gguf \
  Maya-XS/MiniMax-M3.1-Flash-Maya-XS-maya-indexers.bin \
  --revision 9d256f59f1abe27216511c82e3a8bbe4bd0930d0

hf download Mia-AiLab/MiniMax-M3.1-Flash-EXL3-EAQ-v1-3.5-bpw \
  config.json preprocessor_config.json model-vision-00001-of-00001.safetensors \
  'dspark/*' --revision fe796c40546d8b28340c5ed85b892e181ee21dec

hf download peasantsmith/CYBER-FROST-3.8-PS-GUFF \
  CYBER-FROST-3.8-PS-GUFF-Q5_K_M.gguf \
  --revision 32867bb9e228afac427c136dd657b34b7c3f0e86
```

## Preparation and serving

Mount the **whole** cache read-only at `/root/.cache/huggingface` and writable
persistent storage at `/data`. Keep these paths identical during preparation
and serving: pack indexes reference the model files by their absolute paths.
`HF_HOME` can select another cache root when preparing, but that same root
must be mounted when serving.

For the chosen model, mount `maya-config.json` at
`/etc/maya/maya-config.json` and `prepare.sh` at `/etc/maya/prepare.sh`.
Set `MAYA_CONFIG=/data/config/<model>.json`, where `<model>` is `glm-s24`,
`minimax-xs` or `cyber-frost`. Run:

```bash
bash /etc/maya/prepare.sh
/opt/maya/entrypoint.sh serve
```

The scripts only link cached model files and build upstream's runtime packs;
they never download files or copy model blobs. GLM/Qwen pack generation
converts the small dense projections to BF16 as upstream's setup does;
CYBER-FROST also derives its MTP drafter from the GGUF. Generated packs are not
new quantizations of the full model. Subsequent preparation reuses the pack
and refreshes the writable config from its template. After changing preparation
or pack tools, use a fresh data directory or remove only that model's
`/data/<model>/.prepared` marker while its server is stopped.

The scripts refuse to replace an existing model path that is not the expected
symlink. Do not point `/data/<model>` at an unrelated model installation.
`MAYA_CONFIG_TEMPLATE` can override the config template path.

Use the device mounts, permissions and scheduling in [RUNNING.md](../RUNNING.md).
These configs are functional starting points, not performance-tuned settings.
GLM's RAM tier is explicitly capped at 48 GiB across its parts.
MiniMax uses a layer split, not GGUF tensor parallel.

MiniMax's `installer.prefill_calibration` and `installer.speed_calibration`
explicitly record **skipped**, not measured, calibration. Both are necessary:
the v1.1.35 launcher otherwise measures them automatically before serving,
even without `--calibrate`. The engine's `--no-prefill-tune` alone does not
disable the launcher's calibration. These markers keep DSpark enabled by
choice, without a performance claim.

## Smoke runner

`smoke.py` runs the same prepare script twice (idempotence check), starts the
HTTP server, sends short serial arithmetic/Russian/code/conversation requests,
then a colored-shapes image and a blank control for the two image-capable
models. It stops each server before starting the next. Raw HTTP responses,
server logs and preparation logs go to `/data/results/<model>`.
Before launching a GPU engine it also checks the upstream launcher's two
automatic-calibration predicates and refuses a config that would measure speed.

Mount the three model folders under `/work`, then, **only with GPU-run approval**:

```bash
python /work/smoke-v1.1.35/smoke.py glm-s24 minimax-xs cyber-frost
```

The runner's keyword checks are only a first gate. Manually inspect generated
code, language coherence, visual descriptions and the blank-image control;
a successful HTTP response alone is not a quality pass. No timing is scored.
