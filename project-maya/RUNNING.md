# Running Maya

The image contains prebuilt HIP text engines and a CPU `maya-vision` helper.
DeepSeek 4.1 uses its own GPU vision tower inside `maya-ds4`; GLM uses the CPU
helper. Model weights are not part of the image.

Use the same model/data mount paths during preparation and serving. In the
commands below, `/models` contains GGUF files and `/data` is writable persistent
storage. Run preparation commands inside the image, not on the Kubernetes host.

## DeepSeek 4.1: manual JSON

### 1. Prepare the vision tower

Use the original vision weights and upstream's converter. The revision below
is pinned by v1.1.24's `tools/ds4/download_gguf.json`:

```bash
hf download deepseek-ai/DeepSeek-V4.1-Flash-1017 \
  model-00001-of-00048.safetensors config.json \
  --revision 1bae0e1088993b9b82de08f59de5be5a34e42170 \
  --local-dir /data/vision
cd /opt/maya
python tools/ds4/vision_pack.py --dir /data/vision
```

The download is about 971 MB. The converter fetches three image-marker rows
(30 KB plus the safetensors header) from shard 2 using HTTP Range; it does not
download that whole shard. It writes `vision.bin` and `vision.json`, preserving
the checkpoint values. Allow about 1.94 GB for the source and generated pack.
The language-model weights are not downloaded again. DS4's native vision path
does not use `mmproj-F16.gguf`.

### 2. Build the language-model pack

```bash
cd /opt/maya
python tools/ds4/pack_gguf.py \
  --model /models/UD-Q8_K_XL --out /data/ds4 --vision /data/vision
```

This writes an index and tokenizer, not another copy of the weights.
`/models` can remain read-only. The pack records absolute paths to its source
model and relative paths to the vision data: keep all mounts unchanged.

### 3. Write `/data/config/maya-ds4-hip.json`

```json
{
  "exe": "/opt/maya/build-hip/maya-ds4",
  "cwd": "/opt/maya",
  "backend": "hip",
  "gpu": [0, 1, 2, 3],
  "model_name": "deepseek-v4.1-flash",
  "tokenizer": "/data/ds4/tokenizer",
  "log": "/data/maya-ds4.log",
  "args": [
    "--pack", "/data/ds4",
    "--max-context", "8704",
    "--tp", "2",
    "--cpu-threads", "56",
    "--prefill-chunk", "4096",
    "--reserve-mib", "1280",
    "--mmap-experts", "auto",
    "--dspark", "none",
    "--vision", "on"
  ],
  "env": {
    "DS4_RING_MB": "400",
    "DS4_ENGRAM_CACHE_MB": "256",
    "DS4_HIP_ATTN_SWIZZLE": "1",
    "STRATA_DS4_RAM_TIER": "0",
    "STRATA_DS4_DISK_SKIP_W": "0",
    "STRATA_DS4_PROMPT_SKIP": "0"
  }
}
```

Adjust GPU indices, CPU threads and context for your hardware. The extra VRAM
reserve leaves room for vision; measure actual free VRAM under image requests.
The example disables speculative decoding and computation skips. With a 192 GB
RAM limit, do not substitute `--mmap-experts off`: the tested v1.1.24 load tried
to copy 181.7 GB of experts into RAM and was OOM-killed before serving.

### 4. Start the server

Set `MAYA_CONFIG=/data/config/maya-ds4-hip.json` and pass `serve` as the
container arguments. The entrypoint starts the API on `0.0.0.0:8080` without
running setup or downloading weights. Use `serve --api-key YOUR_KEY` when
exposing the API; in Kubernetes obtain the key from a Secret.

## DeepSeek 4.1: through setup

Unlike the manual pack command, upstream setup writes its pack inside the
model directory. For a read-only HF cache, create a writable directory of
symlinks; do not make the snapshot writable or copy its full contents:

```bash
mkdir -p /data/models/UD-Q8_K_XL
ln -s /models/UD-Q8_K_XL/*.gguf /data/models/UD-Q8_K_XL/

/opt/maya/extra/entrypoint.sh setup \
  --model DeepSeek-V4.1-Flash-1017 --ds4-quant gguf-q8 \
  --model-dir /data/models/UD-Q8_K_XL \
  --models-dir /data/models \
  --gpus 0,1,2,3 --context 8704 --vram-reserve-mib 1280 \
  --drafting off --repack --plain \
  --env STRATA_DS4_DISK_SKIP_W=0 --env STRATA_DS4_PROMPT_SKIP=0
```

Answer **n** to the DSpark download offer and **y** to the vision-tower download
offer (about 971 MB). Setup runs its own `tools/ds4/vision_pack.py`, writes the
vision pack to `/data/models/vision`, and adds it to the model index. No custom
conversion scripts or setup patches are needed. If the vision pack is already
there, setup reuses it; `--repack` refreshes the model index.

In v1.1.24, `--drafting off` does not skip the DSpark download offer. Do not pass
`--download-model`: approve only the vision download. If setup offers to download
language-model shards, decline and check the mounts and shard list.

Setup copies the generated JSON to `/data/config/maya-ds4-hip.json`. Review it
before serving: set `--dspark none`, `--mmap-experts auto` and
`"log": "/data/maya-ds4.log"`. The manual JSON above shows the remaining settings
of the tested profile. Use the resulting file with `MAYA_CONFIG` and `serve`.

## GLM vision

Upstream HIP setup leaves GLM vision disabled. Create the text config with
setup, obtain GLM's matching projector/vocabulary files, then add this member
to the JSON yourself; a DeepSeek projector cannot be used for GLM:

```json
"vision": {
  "exe": "/opt/maya/build-vision-cpu/bin/maya-vision",
  "mmproj": "/data/vision/mmproj-GLM-5.3-Flash-F16.gguf",
  "model": "/data/vision/GLM-5.3-Flash-vocab.gguf",
  "gpu": false
}
```

These are the matching files from upstream's
[CPU vision instructions](https://github.com/mw00/project-maya/blob/v1.1.24/docs/AMD_MAYA.md#cpu-image-encoder-on-linux).
The CPU helper is prebuilt using upstream's `glm5next_patch.py`: this adds GLM's
projector to its pinned llama.cpp. No custom setup changes are applied.
DeepSeek does **not** use this `vision` JSON member: its vision tensors belong
to the model pack, and `--vision on` enables the native tower.

## Kubernetes flow

1. Build/publish the image, then pin its tag or digest for both preparation and
   serving. Ensure the node's AMD kernel driver works.
2. Mount writable persistent storage at `/data`, model storage read-only at
   `/models`, and a memory-backed `emptyDir` at `/dev/shm`. Mount an entire HF
   cache rather than just its snapshot when the files are symlinks into `blobs`.
3. Run a preparation Job with the manual commands or setup above. For manual
   preparation override `command` with `["bash", "-ec"]`; otherwise pass
   `["setup", ...]` in `args`, keeping the image entrypoint. Wait for the Job to
   complete before starting inference.
4. Start a Deployment with `replicas: 1`, `strategy: {type: Recreate}`,
   `args: ["serve"]` and `MAYA_CONFIG` pointing at the persistent JSON. Reuse
   exactly the same mount paths and node placement as the preparation Job.
5. Request GPUs using your AMD device plugin. Without a plugin, passing
   `/dev/kfd` and `/dev/dri` requires a device-enabled runtime configuration
   (the test cluster uses a privileged Pod with explicit device mounts).
   Do not combine plugin allocation with arbitrary device visibility overrides.
6. Give the runtime `IPC_LOCK` capability and sufficient CPU/RAM. A memory limit
   of `192G` is 192 GB decimal; `/dev/shm` and the charged file cache count
   against it. Use a startup probe on `/health` with enough time to load the
   model, then a readiness probe. Avoid an aggressive liveness probe during
   long prompts.
7. Inspect preparation/container logs and the engine log named by the JSON.
   Forward the API locally before adding a Service/Ingress:

```bash
kubectl -n YOUR_NAMESPACE logs -f job/maya-setup
kubectl -n YOUR_NAMESPACE logs -f deployment/maya
kubectl -n YOUR_NAMESPACE port-forward deployment/maya 8080:8080
curl -fsS http://127.0.0.1:8080/v1/models
```

Keep model updates and repacking in explicit preparation Jobs, not in the
serving container. Never start a second inference process on already occupied
GPUs just to update the config.

### Existing DS4.1 cache on worker6

Mount `/srv/ml/shared-hf-cache` read-only at `/hf`. The tested snapshot is:

```bash
SNAPSHOT=/hf/hub/models--unsloth--DeepSeek-V4.1-Flash-1017-GGUF/snapshots/60ad3651641b5c97679c807e064ab1d7a3ca1455
cd /opt/maya
python tools/ds4/pack_gguf.py \
  --model "$SNAPSHOT/UD-Q8_K_XL" --out /data/ds4 --vision /data/vision
```

Prepare `/data/vision` with the standard commands in step 1 first. The existing
GGUF language-model shards are reused read-only. Use a separate writable
hostPath for `/data` and pin both preparation and serving to
`kube-worker6.arkprojects.lan`. The test uses `/srv/ml/maya-vision-tests` for
its packs, logs and copied input picture; it does not modify the HF cache.

## Send a picture

Run this on the machine holding the picture after forwarding port 8080:

```bash
python3 - <<'PY'
import base64
import json
from pathlib import Path
import urllib.request

image = Path('/mnt/c/Users/mixa3607/Downloads/IMG_20260922_232444_095.jpg')
payload = {
    'model': 'deepseek-v4.1-flash',
    'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {
            'url': 'data:image/jpeg;base64,' + base64.b64encode(image.read_bytes()).decode()}},
        {'type': 'text', 'text': 'Describe the picture and any readable text.'},
    ]}],
    'reasoning_effort': 'none',
    'max_tokens': 256,
}
request = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',
    data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=600) as response:
    print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
PY
```

Add an `Authorization: Bearer ...` header if you configured an API key.

## gfx906 vision smoke test

Tested v1.1.24 (`75798d4280dc`), ROCm 10.1, max-ILP, 4 x MI50 32 GB,
UD-Q8_K_XL, TP2, context 8704, 56 CPU threads and the manual profile above.
The binaries were built with this Dockerfile and copied into an isolated
ROCm test Pod; the API test used a manually prepared pack and JSON, not setup.
That vision pack was converted from the cached mmproj; these GPU measurements
are not an end-to-end test of the standard safetensors preparation flow above.
No new image was published.

- The supplied picture becomes 966 x 1288 pixels and 746 embedding rows.
  Native GPU encoding takes about 7 seconds; rebuilding gives identical rows.
- `/health` reports `images: true`; `/v1/models` advertises text/image input.
- The image API request correctly describes Firefox-chan, fox ears/tail,
  clothing and the Firefox Add-ons background. A white-image control returns
  “The image is completely blank and contains no visible content.”
- Original-image request: 46.4 s total, 767 prompt tokens at 23.8 tok/s,
  160 generated tokens at 11.4 tok/s. The answer hits the test's 160-token cap.
- Sampled minimum free VRAM: 994 / 1319 / 1002 / 1010 MiB. RAM limit:
  192,000,000,000 bytes; peak charged memory about 192.0 GB including file
  cache. `memory.events`: `max=52`, `oom=0`, `oom_kill=0` — this is a
  cache-reclaiming run at the limit, not a profile with spare RAM.
- GLM's CPU helper builds; end-to-end GLM image inference was not tested.

Worker-side artifacts: `/srv/ml/maya-vision-tests/vision-smoke.json`,
`server.log`, `engine.log`, `setup-final.log`, `manual-config.json` and the
generated packs. Existing services and the read-only HF cache were unchanged.
