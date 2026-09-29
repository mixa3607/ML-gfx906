# Smoke: 2026-09-29, ROCm base

## Проверенный образ

`registry.arkprojects.space/apps/llama.cpp-multiruntime:v0.5.0-rocm-7.14-cuda-13.3.0-rocm-base-smoke`

- Index digest: `sha256:4e22727c4dcab61004d63954c147c817c77caedcb460f9fbe95cd1d73e0f4a7d`.
- linux/amd64 manifest: `sha256:5c941f322ffaf479a3ae369284b7b8c268d437a6e0cccd1636398e74dc37acd2`.
- Сжатые слои: 2 547 952 614 байт (~2.37 GiB).
- В контейнере: `/app` — 163 MiB, `/opt/rocm` — 5.1 GiB,
  `/usr/local/cuda-13.3` — 544 MiB.
- llama.cpp: `v0.5.0`, commit `7fe450e19305b828c199d602c23a8337aaa1f03b`.

Вариант с отдельной CPU/RPC-сборкой на Ubuntu сохранён в commit `035e763`.
Его сжатые слои занимали 0.94 GiB; новый вариант использует готовый полный
ROCm-образ и добавляет только CUDA runtime/backend.

## Окружение

- Kubernetes node: `kube-worker6.arkprojects.lan`.
- Namespace: `ns-vllm`, deployment: `llama-cpp-multiruntime-llamacpp`.
- NVIDIA: 2 × GeForce RTX 5060 Ti, driver `595.91.07`.
- AMD: 4 × gfx906, определяются как `AMD Instinct MI60 / MI50`, 32752 MiB каждый.
- CPU backend автоматически выбран `libggml-cpu-icelake.so`.
- Модель: `ggml-org/models/tinyllamas/stories260K.gguf`.
- SHA256 модели: `270cba1bd5109f42d03350f60406024560464db173c0e387d91f0426d3bd256d`.

## Результаты

| Проверка | Результат |
| --- | --- |
| ELF-зависимости CUDA/HIP/RPC | PASS, все разрешены в pod |
| Загрузка CUDA + ROCm + RPC + CPU в одном процессе | PASS |
| Перечисление устройств | PASS, CUDA0–1 и ROCm0–3 |
| CPU, 8 токенов | PASS, 0/6 слоёв offload |
| CUDA0 и CUDA1, по 8 токенов | PASS, 6/6 слоёв offload на каждом |
| ROCm0–3, по 8 токенов | PASS, 6/6 слоёв offload на каждом |
| CUDA0 + ROCm0, 8 токенов | PASS, GPU model buffers на обоих backend |
| RPC → локальный CPU, handshake + 8 токенов | PASS |
| llama-server на CUDA0 + ROCm0, `/health` | PASS, `{"status":"ok"}` |
| HTTP `/completion`, `n_predict=8` | PASS, 8 токенов: `, there was a little girl` |

Параметры генерации: контекст 256, batch/ubatch 32, 2 CPU threads, seed 1,
temperature 0, `--no-warmup`; mixed: `--split-mode layer --tensor-split 1,1`.
HTTP smoke использовал loopback `127.0.0.1:8081` и один slot.
Проведены только smoke-проверки.

Логи в dev-pod: `/tmp/llama-smoke.aR0NTM/`, `/tmp/llama-http-smoke.log`,
`/tmp/llama-http-response.json`. После тестов RPC/HTTP процессы остановлены,
dev-pod оставлен с `sleep infinity`.
