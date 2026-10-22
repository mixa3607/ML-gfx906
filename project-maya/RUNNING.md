# Running Maya

The image contains prebuilt HIP text engines (`maya`, `maya-ds4`), the CPU
`maya-vision` helper, upstream tools and their Python dependencies. Model
weights are not part of the image.

Use the same cache and data mount paths during preparation and serving. The
language model is read from a Hugging Face cache mounted where the HF library
expects it, `/root/.cache/huggingface`; `/data` is writable persistent storage.
Run preparation commands inside the image, for example:

```bash
HF_CACHE=/srv/ml/shared-hf-cache
docker run --rm -it \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add "$(getent group render | cut -d: -f3)" \
  --cap-add IPC_LOCK --shm-size 2g --ulimit memlock=-1:-1 \
  -v "$PWD/data:/data" -v "$HF_CACHE:/root/.cache/huggingface" \
  --entrypoint bash YOUR_IMAGE
```

Replace `/srv/ml/shared-hf-cache` with the directory that holds the HF cache on
your host (or use a PVC that contains it). Without a shared cache, download the
GGUF files anywhere and mount that directory at `/models` instead; the pack
command below takes the model directory as an argument.

## DeepSeek 4.1: manual preparation

This path is reproducible and needs no interactive prompts, so it is suitable
for Kubernetes preparation Jobs.

### 1. Vision tower

The revision and files are pinned by upstream's
`tools/ds4/download_gguf.json`. The image includes the `hf` CLI; it downloads
into the shared cache, which must be writable:

```bash
MAYA_REV=1bae0e1088993b9b82de08f59de5be5a34e42170
hf download deepseek-ai/DeepSeek-V4.1-Flash-1017 \
  model-00001-of-00048.safetensors config.json \
  --revision "$MAYA_REV"

VISION_SNAP=/root/.cache/huggingface/hub/models--deepseek-ai--DeepSeek-V4.1-Flash-1017/snapshots/$MAYA_REV
mkdir -p /data/vision
ln -sf "$VISION_SNAP/model-00001-of-00048.safetensors" /data/vision/
ln -sf "$VISION_SNAP/config.json" /data/vision/

cd /opt/maya
python tools/ds4/vision_pack.py --dir /data/vision
```

Allow about 2 GB for the cached shard and the generated `vision.bin` /
`vision.json`. This is separate from the language-model cache and is downloaded
once. The converter reads the three image-marker rows from shard 2 with an HTTP
Range request, so that whole shard is not downloaded. DS4's native vision path
does not use the cached `mmproj-F16.gguf`.

### 2. Build the language-model pack

The cache already contains the language model. The snapshot below is an
example; use the snapshot that is present in your cache:

```bash
SNAPSHOT=/root/.cache/huggingface/hub/models--unsloth--DeepSeek-V4.1-Flash-1017-GGUF/snapshots/60ad3651641b5c97679c807e064ab1d7a3ca1455
cd /opt/maya
python tools/ds4/pack_gguf.py \
  --model "$SNAPSHOT/UD-Q8_K_XL" --out /data/ds4 --vision /data/vision
```

This writes an index and tokenizer, not another copy of the weights. The pack
records absolute paths under `/root/.cache/huggingface`, so mount the same
cache at the same path when serving. Do not copy the 500 GB of GGUF shards into
`/data`.

### 3. Write `/data/config/maya-ds4-hip.json`

The values below are a starting point for four MI50s; adjust GPU indices, CPU
threads and context for your hardware. The extra VRAM reserve leaves room for
vision; measure the actual free VRAM under image requests.

```json
{
  "exe": "/opt/maya/build-hip/maya-ds4",
  "cwd": "/opt/maya",
  "backend": "hip",
  "gpu": [0, 1, 2, 3],
  "model_name": "deepseek-v4.1-flash",
  "tokenizer": "/data/ds4/tokenizer",
  "log": "/data/maya-ds4.log",
  "lib_dirs": ["/opt/rocm/lib"],
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
    "MAYA_DS4_RAM_TIER": "0",
    "MAYA_DS4_DISK_SKIP_W": "0",
    "MAYA_DS4_PROMPT_SKIP": "0"
  }
}
```

The example disables speculative decoding and computation skips. With a 192 GB
RAM limit, do not substitute `--mmap-experts off`: it tries to copy the experts
into RAM and can be OOM-killed before serving.

### 4. Start the server

```bash
HF_CACHE=/srv/ml/shared-hf-cache
docker run -d --name maya \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add "$(getent group render | cut -d: -f3)" \
  --cap-add IPC_LOCK --shm-size 2g --ulimit memlock=-1:-1 \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/data:/data" -v "$HF_CACHE:/root/.cache/huggingface" \
  -e MAYA_CONFIG=/data/config/maya-ds4-hip.json \
  YOUR_IMAGE serve
```

The entrypoint runs `maya.py`, which validates the config, pack and engine,
then starts the API and dashboard on `0.0.0.0:8080`. Pass `--api-key YOUR_KEY`
after `serve` when exposing the API; in Kubernetes obtain the key from a
Secret. The same flags can be set in the config.

## DeepSeek 4.1: through setup

Upstream setup writes its pack inside the model directory, so do not point it
at the shared cache; use the manual path above for the cluster cache. The setup
path is for a separate writable model directory:

```bash
docker run --rm -it \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add "$(getent group render | cut -d: -f3)" \
  --cap-add IPC_LOCK --shm-size 2g --ulimit memlock=-1:-1 \
  -v "$PWD/data:/data" -v /path/to/writable-models:/models \
  YOUR_IMAGE setup \
  --model DeepSeek-V4.1-Flash-1017 --ds4-quant gguf-q8 \
  --model-dir /models/UD-Q8_K_XL \
  --models-dir /models \
  --gpus 0,1,2,3 --context 8704 --vram-reserve-mib 1280 \
  --drafting off --repack \
  --env MAYA_DS4_DISK_SKIP_W=0 --env MAYA_DS4_PROMPT_SKIP=0
```

Setup asks before downloading model files, the DSpark drafter and the vision
tower. Approve only what you need; the drafter is optional. The entrypoint
copies the generated `maya-*-hip.json` files to `/data/config/`. Review the
DeepSeek config before serving: ensure `--dspark none`, add
`--mmap-experts auto`, and set `"log"` to a path on `/data`.

Do not run this interactive setup as a Kubernetes Job; use the manual path
above for unattended preparation.

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
The CPU helper is prebuilt with upstream's `glm5next_patch.py`, which adds
GLM's projector to its pinned llama.cpp. DeepSeek does **not** use this
`vision` member: its vision tensors belong to the model pack, and `--vision on`
enables the native tower.

## Kubernetes

1. Build/publish the image, then pin its tag or digest for both preparation and
   serving. Ensure the node's AMD kernel driver works.
2. Mount writable persistent storage at `/data`, the shared HF cache at
   `/root/.cache/huggingface`, and a memory-backed `emptyDir` at `/dev/shm`.
   Mount the whole cache, not just a snapshot, because its files are symlinks
   into `blobs/`. The cache must be writable so `hf` can add the vision files.
   Example paths are `/srv/ml/maya` for `/data` and
   `/srv/ml/shared-hf-cache` for the cache:

```yaml
extraVolumes:
  - name: maya-data
    hostPath:
      path: /srv/ml/maya
  - name: shared-hf-cache
    hostPath:
      path: /srv/ml/shared-hf-cache
extraVolumeMounts:
  - name: maya-data
    mountPath: /data
  - name: shared-hf-cache
    mountPath: /root/.cache/huggingface
```

   Use the `shared-hf-cache` PVC instead of `hostPath` where it is available,
   or the equivalent `volumes` / `volumeMounts` in a plain manifest.
3. Run a preparation Job with the manual commands above. Override `command`
   with `["bash", "-ec"]` and the commands as its argument; keep the image
   entrypoint for the serving Deployment. Wait for the Job to complete before
   starting inference.
4. Start a Deployment with `replicas: 1`, `strategy: {type: Recreate}`,
   `args: ["serve"]` and `MAYA_CONFIG` pointing at the persistent JSON. Reuse
   exactly the same `/data` and `/root/.cache/huggingface` mounts and node
   placement as the preparation Job.
5. Request GPUs using your AMD device plugin. Without a plugin, passing
   `/dev/kfd` and `/dev/dri` requires a device-enabled runtime configuration
   (the test cluster used a privileged Pod with explicit device mounts).
6. Give the runtime `IPC_LOCK` and sufficient CPU/RAM. A memory limit of
   `192G` is 192 GB decimal; `/dev/shm` and the charged file cache count
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

## Send a picture

With port 8080 forwarded:

```bash
python3 - "$PWD/image.jpg" <<'PY'
import base64
import json
import sys
import urllib.request
from pathlib import Path

image = Path(sys.argv[1])
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
request = urllib.request.Request(
    'http://127.0.0.1:8080/v1/chat/completions',
    data=json.dumps(payload).encode(),
    headers={'Content-Type': 'application/json'})
with urllib.request.urlopen(request, timeout=600) as response:
    print(json.dumps(json.load(response), ensure_ascii=False, indent=2))
PY
```

Add an `Authorization: Bearer ...` header if you configured an API key.

## Validation

Tested with upstream v1.1.24 (`75798d4280dc`), ROCm 10.1, four MI50 32 GB,
UD-Q8_K_XL, TP2, context 8704 and 56 CPU threads.

- DS4's native GPU vision tower encodes a test picture in about 7 seconds and
  gives identical rows when rebuilt. `/health` reports `images: true`, and
  `/v1/models` advertises text/image input.
- A real image request returned a correct description; a blank-image control
  returned "The image is completely blank and contains no visible content."
- GLM's CPU vision helper builds. End-to-end GLM image inference was not tested.
