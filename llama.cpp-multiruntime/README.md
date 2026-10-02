# llama.cpp multiruntime

Ubuntu 24.04, одно ядро llama.cpp и четыре динамических backend: CPU, RPC,
ROCm (gfx906) и CUDA (sm120).

Тестовый образ: `registry.arkprojects.space/apps/llama.cpp-multiruntime:v0.5.0-rocm-7.14-cuda-13.3.0-rocm-base-smoke`.

## Состав

- Основа — готовый `mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14`:
  llama.cpp, CPU/RPC/HIP backend, ROCm и инструменты уже установлены.
- Поверх через APT устанавливаются `cuda-cudart-13-3=13.3.29-1` и
  `libcublas-13-3=13.5.1.27-1`. cuDNN для этого backend не требуется.
- Из `mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn` копируется только
  `/app/libggml-cuda.so`.
- Оба образа закреплены по digest.

## Сборка

```bash
./llama.cpp-multiruntime/build-and-push.image.sh

# Локальная загрузка вместо push (в том числе при remote buildx):
LLAMA_PUSH=0 ./llama.cpp-multiruntime/build-and-push.image.sh
```

Настройки находятся в `env.sh`, переменные окружения имеют приоритет.
Дополнительные buildx-аргументы можно передать скрипту.

Запуск наследуется от ROCm-образа (`/app/entrypoint.sh`). Конкретный инструмент
можно выбрать через `--entrypoint /app/llama-server`, `/app/llama-cli` или
`/app/ggml-rpc-server`.

## Запуск на GPU

```bash
docker run --rm --gpus all --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render \
  --entrypoint /app/llama-cli \
  registry.arkprojects.space/apps/llama.cpp-multiruntime:v0.5.0-rocm-7.14-cuda-13.3.0-rocm-base-smoke --list-devices
```

CUDA driver (`libcuda.so.1`) предоставляет NVIDIA Container Toolkit на хосте.
В Kubernetes нужны `runtimeClassName: nvidia`, `NVIDIA_VISIBLE_DEVICES` и доступ
к `/dev/kfd`, `/dev/dri`. Имена устройств: `CUDA0`, `CUDA1`, `ROCm0`…`ROCm3`.
Пример смешанного размещения: `--device CUDA0,ROCm0 --split-mode layer`.
CPU выбирается через `--device none -ngl 0`.

## Smoke-тест

Результаты проверки в текущем кластере: [SMOKE.md](./SMOKE.md).
Практическая проверка Gemma 4 31B с MTP на NVIDIA: [GEMMA4-MTP.md](./GEMMA4-MTP.md).
DSpark Q8 на NVIDIA и AMD: [GEMMA4-DSPARK.md](./GEMMA4-DSPARK.md).
Vendor DSpark для LiquidAI LFM2.5-VL-3B Q8: [LFM25-VL-DSPARK.md](./LFM25-VL-DSPARK.md).
Разделение MoE-экспертов между CUDA и ROCm на Gemma 4 26B-A4B Q8: [GEMMA4-26B-MOE-SPLIT.md](./GEMMA4-26B-MOE-SPLIT.md).
DeepSeek V4 Flash на шести GPU с уменьшенным CPU-offload: [DS4F-SIXGPU.md](./DS4F-SIXGPU.md).

Отдельный `smoke-test.sh` проверяет зависимости backend, регистрацию CPU/RPC,
наличие двух CUDA и четырёх ROCm GPU и RPC handshake с локальным CPU-сервером.
Ожидаемые количества меняются через `SMOKE_CUDA_DEVICES` / `SMOKE_ROCM_DEVICES`.
При заданном `SMOKE_MODEL` дополнительно генерирует по 8 токенов на CPU,
каждом CUDA/ROCm GPU, CUDA0+ROCm0 и RPC/CPU, проверяя размещение GPU-буферов.
Контекст — 256 токенов, таймаут каждого
запуска — 120 секунд. Логи сохраняются в `/tmp/llama-smoke.*`.

Для текущего кластера добавлен release `llama-cpp-multiruntime` в
`/home/mixa3607/k3s/kube/ns-vllm/llama.cpp-amd-dev/helmfile.yaml`:

```bash
helmfile -f /home/mixa3607/k3s/kube/ns-vllm/llama.cpp-amd-dev/helmfile.yaml \
  -l name=llama-cpp-multiruntime sync

# Из корня ML-gfx906: скопировать тест в pod и запустить вручную.
kubectl -n ns-vllm exec -i deployment/llama-cpp-multiruntime-llamacpp -- \
  sh -c 'cat > /tmp/smoke-test.sh' < llama.cpp-multiruntime/smoke-test.sh
kubectl -n ns-vllm exec deployment/llama-cpp-multiruntime-llamacpp -- bash /tmp/smoke-test.sh
```

Небольшая модель для проверки вычислений:

```bash
kubectl -n ns-vllm exec deployment/llama-cpp-multiruntime-llamacpp -- \
  curl -fL https://huggingface.co/ggml-org/models/resolve/main/tinyllamas/stories260K.gguf \
  -o /tmp/stories260K.gguf
kubectl -n ns-vllm exec deployment/llama-cpp-multiruntime-llamacpp -- \
  env SMOKE_MODEL=/tmp/stories260K.gguf bash /tmp/smoke-test.sh
```

Dev-pod по умолчанию выполняет `sleep infinity`; тест запускается вручную.
