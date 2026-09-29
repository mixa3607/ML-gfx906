# llama.cpp multiruntime

Ubuntu 24.04, одно ядро llama.cpp и четыре динамических backend: CPU, RPC,
ROCm (gfx906) и CUDA (sm120).

Тестовый образ: `registry.arkprojects.space/apps/llama.cpp-multiruntime:v0.5.0-rocm-7.14-cuda-13.3.0-smoke`.

## Состав

- Из исходников `ggml-org/llama.cpp`, тег `v0.5.0`, commit
  `7fe450e19305b828c199d602c23a8337aaa1f03b` собираются общие библиотеки,
  CLI/server/tools, RPC и все CPU-варианты (`GGML_NATIVE=OFF`).
- Из `mixa3607/llama.cpp-gfx906:v0.5.0-rocm-7.14` копируется только
  `/app/libggml-hip.so`.
- Из `mixa3607/llama.cpp-sm120:v0.5.0-cuda-13.3.0-cudnn` копируется только
  `/app/libggml-cuda.so`.
- Оба образа закреплены по digest. Сборка проверяет commit исходников и версии
  доноров: динамические backends должны соответствовать общему ядру.
- Через APT устанавливаются `amdrocm-runtime7.14`, `amdrocm-blas7.14-gfx906`,
  `amdrocm-rccl7.14-gfx906` и их зависимости, `cuda-cudart-13-3=13.3.29-1`,
  `libcublas-13-3=13.5.1.27-1`. cuDNN для этого CUDA backend не требуется.
  ROCm LLVM/COMGR и solver входят в runtime-зависимости пакетов BLAS/HIP.
- `/app/runtime-packages.txt` содержит установленные версии пакетов,
  `/app/llama-commit.txt` — полный commit ядра.

## Сборка

```bash
./llama.cpp-multiruntime/build-and-push.image.sh

# Локальная загрузка вместо push (в том числе при remote buildx):
LLAMA_PUSH=0 ./llama.cpp-multiruntime/build-and-push.image.sh
```

Настройки находятся в `env.sh`, переменные окружения имеют приоритет.
Дополнительные buildx-аргументы можно передать скрипту, например
`--build-arg BUILD_JOBS=4`. При обновлении llama.cpp нужно одновременно обновить
commit/tag ядра и оба donor image; версии runtime должны соответствовать донорам.

По умолчанию запускается `/app/llama-server --host 0.0.0.0 --port 8080`.
Для других инструментов используйте `--entrypoint /app/llama-cli` или
`--entrypoint /app/ggml-rpc-server`. При передаче аргументов серверу указывайте
`--host 0.0.0.0`, если нужен доступ извне контейнера.

## Запуск на GPU

```bash
docker run --rm --gpus all --device /dev/kfd --device /dev/dri \
  --group-add video --group-add render \
  --entrypoint /app/llama-cli \
  registry.arkprojects.space/apps/llama.cpp-multiruntime:v0.5.0-rocm-7.14-cuda-13.3.0-smoke --list-devices
```

CUDA driver (`libcuda.so.1`) предоставляет NVIDIA Container Toolkit на хосте.
В Kubernetes нужны `runtimeClassName: nvidia`, `NVIDIA_VISIBLE_DEVICES` и доступ
к `/dev/kfd`, `/dev/dri`. Имена устройств: `CUDA0`, `CUDA1`, `ROCm0`…`ROCm3`.
Пример смешанного размещения: `--device CUDA0,ROCm0 --split-mode layer`.
CPU выбирается через `--device none -ngl 0`.

## Smoke-тест

Результаты проверки в текущем кластере: [SMOKE.md](./SMOKE.md).

`/app/smoke-test.sh` проверяет зависимости backend, регистрацию CPU/RPC,
наличие двух CUDA и четырёх ROCm GPU и RPC handshake с локальным CPU-сервером.
Ожидаемые количества меняются через `SMOKE_CUDA_DEVICES` / `SMOKE_ROCM_DEVICES`.
При заданном `SMOKE_MODEL` дополнительно генерирует по 8 токенов на CPU,
каждом CUDA/ROCm GPU, CUDA0+ROCm0 и RPC/CPU, проверяя размещение GPU-буферов.
Контекст — 256 токенов, таймаут каждого
запуска — 120 секунд. Логи сохраняются в `/tmp/llama-smoke.*`.

Для текущего кластера добавлен release `llama-cpp-multiruntime` в
`/home/mixa3607/k3s/kube/ns-vllm/llama.cpp-amd-dev/helmfile.yaml`:

```bash
cd /home/mixa3607/k3s/kube/ns-vllm/llama.cpp-amd-dev
helmfile -l name=llama-cpp-multiruntime sync
kubectl -n ns-vllm exec deployment/llama-cpp-multiruntime-llamacpp -- /app/smoke-test.sh
```

Небольшая модель для проверки вычислений:

```bash
kubectl -n ns-vllm exec deployment/llama-cpp-multiruntime-llamacpp -- \
  curl -fL https://huggingface.co/ggml-org/models/resolve/main/tinyllamas/stories260K.gguf \
  -o /tmp/stories260K.gguf
kubectl -n ns-vllm exec deployment/llama-cpp-multiruntime-llamacpp -- \
  env SMOKE_MODEL=/tmp/stories260K.gguf /app/smoke-test.sh
```

Dev-pod по умолчанию выполняет `sleep infinity`; тест запускается вручную.
