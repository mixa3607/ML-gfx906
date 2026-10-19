# Strata gfx906

[Strata](https://github.com/Niko1221/Strata) inference image for AMD `gfx906`.
The engine and GPU vision encoder are built into the image. CPU vision is
included as a fallback; model weights are downloaded separately.

## Build

Requires Docker Buildx and the [ROCm base image](../rocm/README.md).
Log in to the destination registry and run from this directory:

```bash
export STRATA_IMAGE=registry.arkprojects.space/apps/strata-gfx906
./build-and-push.image.sh
```

The script builds and pushes, skipping existing tags; `STRATA_FORCE_BUILD=1`
forces a rebuild. Defaults are in the [preset](./preset.v0.2.0-beta-rocm-10.1.sh)
and [build script](./build-and-push.image.sh).

## Run

Set your image tag and replace `./data` with your model-data directory if needed:

```bash
IMAGE=registry.arkprojects.space/apps/strata-gfx906:YOUR_TAG
mkdir -p ./data

docker run -d --name strata \
  --device /dev/kfd --device /dev/dri \
  --group-add video --group-add "$(getent group render | cut -d: -f3)" \
  --ulimit memlock=-1:-1 --shm-size 2g --stop-timeout 120 \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/data:/data" \
  -e MODEL=IQ3_XXS -e CONTEXT=32k -e VISION=gpu -e TUNE=skip \
  "$IMAGE"
```

The first start downloads and prepares the model. Models, settings and the
generated API key persist in `/data`. The API is published on localhost.
After startup, retrieve the key and check the API:

```bash
KEY=$(docker exec strata strata launch --show-key --preset docker)
curl -fsS -H "Authorization: Bearer $KEY" http://127.0.0.1:8080/v1/models
```

Model selection and other settings follow the
[upstream Docker documentation](https://github.com/Niko1221/Strata/blob/v0.2.0-beta/docs/DOCKER.md).
