# Strata gfx906

[Strata](https://github.com/Niko1221/Strata) inference image for AMD `gfx906`.
The engine and GPU vision encoder are built into the image. CPU vision is
included as a fallback; model weights are downloaded separately.

## Build

Requires Docker Buildx and access to the [ROCm base image](../rocm/README.md).
Log in to the destination registry, then run from this directory:

```bash
export STRATA_IMAGE=registry.arkprojects.space/apps/strata-gfx906
./build-and-push.image.sh
```

The script builds and pushes the image, or skips it if the tag already exists.
Use `STRATA_FORCE_BUILD=1` to rebuild. Logs are saved in `./logs/`.

Defaults live in [build-and-push.image.sh](./build-and-push.image.sh).
The main overrides are:

| Variable                | Purpose                        |
| ----------------------- | ------------------------------ |
| `STRATA_IMAGE`          | Destination image repository   |
| `STRATA_BRANCH`         | Upstream tag or branch         |
| `STRATA_COMMIT`         | Optional commit pin            |
| `STRATA_BASE_IMAGE`     | Full ROCm base-image reference |
| `STRATA_CCACHE_MAXSIZE` | Compiler cache size            |

The Dockerfile targets gfx906. When changing the upstream version, check that
the [patch](./build-context/patch/gfx906-setup.patch) still applies.

## Run

Use any host directory for model data. The examples use `./data`, mounted as
`/data` inside the container. Replace the host side of the mount with your own
directory; no particular disk layout is required.

A local SSD/NVMe is recommended: Strata reads model data during inference,
so network storage can slow it down. When copying a Hugging Face cache,
include the blobs referenced by snapshot symlinks.

The example below uses Qwen3.8-Flash-Next Q4_K_M on four GPUs. Text and GPU
vision were tested on four MI50 cards with this model.

Set `IMAGE` to the image tag you built or pulled:

```bash
IMAGE=registry.arkprojects.space/apps/strata-gfx906:YOUR_TAG
mkdir -p ./data/gguf
```

### Prepare the model

Place all four [`Q4_K_M` GGUF shards](https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF) in `./data/gguf/`. 
For vision, also place [`mmproj-Qwen3.8-Flash-Next-BF16.gguf`](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF) in `./data/`.

Create the Strata pack from the first shard:

```bash
docker run --rm \
  -v "$PWD/data:/data" \
  "$IMAGE" \
  env STRATA_GGUF_PY=/opt/strata/third_party/llama.cpp/gguf-py \
  python3 tools/iq_pack.py \
    --gguf /data/gguf/Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf \
    --out /data/pack --compat-bf16
```

Keep the original GGUF files: the pack references them.

### Configure the server

Save this as `./data/config.json`. Adjust paths and GPU indices
to your machine. The memory and context settings below are from the tested
four-card setup, not general sizing recommendations.

```json
{
  "exe": "/opt/strata/engine/strata",
  "cwd": "/opt/strata",
  "args": [
    "--pack", "/data/pack",
    "--native", "/data/gguf/Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf",
    "--gpu", "0,1,2,3", "--layer-split", "auto",
    "--resident-budget-gib", "32",
    "--expert-profile", "/opt/strata/data/expert-profile.bin",
    "--expert-cache", "auto", "--prefill", "512", "--spec", "4",
    "--max-context", "4096", "--kv", "int8", "--pool-workers", "16",
    "--memory-limit-mib", "122880",
    "--vision", "--vram-reserve-mib", "700"
  ],
  "tokenizer": "/data/pack/tokenizer",
  "model_name": "bartowski/Qwen3.8-Flash-Next-GGUF:Q4_K_M",
  "log": "/data/engine.log",
  "vision": {
    "exe": "/opt/strata/engine/strata-vision-hip",
    "cpu_exe": "/opt/strata/engine/strata-vision",
    "mmproj": "/data/mmproj-Qwen3.8-Flash-Next-BF16.gguf",
    "model": "/data/gguf/Qwen3.8-Flash-Next-Q4_K_M-00001-of-00004.gguf",
    "gpu": true,
    "max_tokens": 1024
  }
}
```

### Start the API

```bash
docker run --rm --privileged --ipc=host --memory=120g \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/data:/data" \
  "$IMAGE" \
  python3 -m serve.server --engine strata --config /data/config.json \
    --host 0.0.0.0 --port 8080 --offline
```

This gives the container GPU access and exposes the API only on the host's
loopback interface, without authentication. The GPU tests used a privileged
Kubernetes pod; the Docker command above uses the same server configuration.

- Health: `http://127.0.0.1:8080/health`
- Chat API: `http://127.0.0.1:8080/v1/chat/completions`
- Engine log: `./data/engine.log`

The vision config selects `strata-vision-hip --gpu`. If it cannot start,
Strata logs a switch to the CPU reader. Check the log if image processing is
unexpectedly slow.

Without an explicit command, the image runs upstream `python3 setup.py`.
Pass setup options as CLI arguments, not the old wrapper's `MODEL`, `GPUS`
or `VISION` environment variables.
