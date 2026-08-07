# Цикл поиска узких мест для GFX906

Этот документ описывает воспроизводимый цикл исследования производительности
llama.cpp на AMD Instinct MI50 (`gfx906`). Его цель - вернуть PP уровня ROCm
6.3.3 и сохранить преимущества TG ROCm 7.14 без изменений исходного кода
llama.cpp, если это возможно.

## Метрики и границы задачи

- **PP**: строка `n_prompt=2048, n_gen=0` из `llama-bench`; обработка prompt.
- **TG**: строка `n_prompt=0, n_gen=256`; генерация токенов.
- Основной тест: один GPU, `--split-mode layer --device ROCm0`, `n_depth=0`.
- Отдельные обязательные проверки: `n_depth=16384,32768`, 2 и 4 GPU, `layer`
  и `tensor`, когда кандидат прошел single-GPU baseline.
- Значимым считать изменение, большее типичного разброса. Ориентир: не менее
  2% при CV меньше 1%; иначе повторить измерение.

Не смешивать PP и TG в одну целевую функцию: у них разные hot paths и
оптимизация PP может ухудшить TG.

## 1. Зафиксировать baseline

Перед изменением зафиксировать все переменные в отдельном каталоге результатов:

```bash
git -C /llama.cpp-upstream-build rev-parse HEAD
hipcc --version
rocminfo
env | sort
```

Сохранить также:

- `CMakeCache.txt`;
- `compile_commands.json`;
- `sha256sum` для `libggml-hip.so`;
- `ldd libggml-hip.so`;
- точную команду benchmark;
- raw JSONL, не только итоговую таблицу.

Для сравнения ROCm 6.3.3 и 7.14 должны совпадать commit llama.cpp, модель,
GGUF revision, параметры benchmark, GPU, порядок `HIP_VISIBLE_DEVICES` и число
потоков CPU. Версии HIP/rocBLAS/hipBLAS фиксировать отдельно: они являются
потенциальной причиной разницы, даже если менялся только компилятор.

## 2. Стабилизировать измерение

1. Не запускать другие GPU workloads на узле.
2. Использовать один и тот же GPU для initial A/B (`ROCm0`).
3. Выполнять варианты в чередующемся порядке: `stock -> candidate -> stock`.
4. Смотреть не только `avg_ts`, но и `samples_ts`/`stddev_ts`.
5. Отмечать thermal/frequency drift, если первый и последний stock различаются.
6. Не делать вывод по multi-GPU данным с большим разбросом: сначала объяснить
   single-GPU результат.

Минимальный benchmark:

```bash
./llama-bench \
  --hf-repo unsloth/Qwen3.5-9B-GGUF:Q8_0 --flash-attn on \
  --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
  --n-gen 256 --n-depth 0 --split-mode layer --device ROCm0 \
  --output jsonl
```

Запускать аналогичный тест с Gemma-4-26B A4B Q4_K_L. Нужны минимум две модели
с разными quantization/kernel mix: один GGUF не представляет весь backend.

## 3. Локализовать фазу и библиотеку

Сначала ответить на два вопроса:

1. Регрессия в PP, TG или обоих режимах?
2. Время в custom ggml HIP kernels или в rocBLAS/hipBLAS?

Собрать kernel profile для каждой проблемной пары `модель x фаза`:

```bash
rocprofv3 --kernel-trace --stats --summary --summary-output-file stdout -- \
  ./llama-bench ... --n-prompt 2048 --n-gen 0 --output jsonl
```

В отчете rocprof сравнивать для каждого kernel:

- `CALLS`: число dispatch должно быть одинаковым для сопоставимых запусков;
- `DURATION`: суммарное время, основной критерий влияния;
- `AVERAGE`, `MIN`, `MAX`, `STDDEV`: длительность одного dispatch и ее
  стабильность;
- `PERCENT (INC)`: доля во времени GPU.

Если изменилась `CALLS`, проблема может быть выше compiler codegen: выбор
алгоритма, shape, graph capture, runtime dispatch или model path. Если calls
одинаковы, а duration изменилась, сравнивать codegen данного kernel.

## 4. Сформировать гипотезу

### Custom HIP kernel горячий

Признаки: `mul_mat_q`, `flash_attn_*`, `rms_norm_*` или другой ggml kernel
занимает заметную долю профиля.

Проверять:

- применен ли флаг к device compile command в `compile_commands.json`;
- регистры, spills, LDS и occupancy для затронутого HSACO;
- изменения в ISA: число memory ops, waitcnt, MFMA/VALU mix, unroll;
- scheduler strategy и register-pressure policy LLVM.

Для GFX906 особенно важны границы allocation VGPR/SGPR: небольшое изменение
регистров может уменьшить waves per CU.

### rocBLAS/hipBLAS kernel горячий

Признак: имя kernel в rocprof похоже на Tensile/rocBLAS solution, а не на
`ggml`/C++ template.

Проверять:

- версии `rocblas`, `hipblas`, `hipblaslt` и их shared-library paths;
- выбранный solution и параметры GEMM;
- наличие/совместимость gfx906 Tensile files;
- изменение формы матриц, batch или stride между версиями.

LLVM flags для llama.cpp не исправят уже предкомпилированное rocBLAS kernel.

### Runtime или multi-GPU горячий

Признаки: profiling показывает существенные RCCL, copy, gaps между kernels,
либо single-GPU стабилен, а 2/4 GPU нет.

Проверять:

- `librccl.so` path и версию;
- topology и порядок GPU;
- split mode (`layer` против `tensor`);
- размер коммуникаций, overlap compute/communication;
- `HIP_VISIBLE_DEVICES` и CPU/NUMA affinity.

## 5. Менять ровно одну переменную

Для scheduler гипотезы собирать отдельные build directories. Не переиспользовать
objects между разными `CMAKE_HIP_FLAGS`.

Начальная матрица для LLVM 23:

| Вариант | Флаг |
| --- | --- |
| stock | _(пусто)_ |
| max-ilp | `-mllvm -amdgpu-sched-strategy=max-ilp` |
| maxocc | `-mllvm -amdgpu-sched-strategy=iterative-maxocc` |
| memory clause | `-mllvm -amdgpu-sched-strategy=max-memory-clause` |
| relaxed occupancy | `-mllvm -amdgpu-schedule-relaxed-occupancy` |

Не комбинировать флаги на первом проходе. После нахождения работающего
направления проверять один параметр за раз, например
`-amdgpu-schedule-metric-bias=50` или `-unroll-threshold=100`.

Каждый кандидат обязан пройти:

1. Single-GPU PP и TG на Qwen и Gemma.
2. rocprof для тех фаз, которые изменились более чем на 2%.
3. Long-context PP/TG.
4. 2/4 GPU проверки только после успешных single-GPU тестов.

## 6. Сравнить kernel attribution, а не только tokens/s

Итоговый результат требуется объяснить суммой hot kernels.

Пример из проверки 2026-08-06:

- Qwen Q8 PP dominated `mul_mat_q<ggml_type=8>`.
- Gemma Q4_K PP dominated `mul_mat_q<ggml_type=12,13,14>`.
- `iterative-maxocc` ускорил Qwen type 8, но катастрофически замедлил Gemma
  types 12/13/14.
- `max-ilp` ускорил оба набора и вернул PP к baseline ROCm 6.3.3.

Если один флаг улучшает один specialization и ломает другой, не выпускать его
глобально. Следующий уровень исследования - разделить device translation units
или назначать LLVM function attribute точечно. Делать это только если нет
глобального флага, успешно проходящего репрезентативную матрицу.

## 7. Критерии принятия

Кандидат можно считать готовым к image build, если:

- PP на тестовых моделях не хуже целевого baseline с учетом разброса;
- TG не регрессирует относительно 7.14 stock больше установленного бюджета;
- no correctness failures в benchmark;
- compile commands подтверждают наличие intended flags в HIP compilation;
- профили объясняют ключевое изменение hot kernels;
- результаты и окружение сохранены в versioned directory.

Для текущего набора это выполняет `max-ilp`:

```bash
. ./preset.b10288-rocm-7.14-maxilp.sh
./build-and-push.image.sh
```

## Файлы эксперимента

- Runner: `run-scheduler-check.sh`
- Первый проведенный эксперимент: `scheduler-check-20260806.md`
- Raw artifacts: `results-20260806/`
- Production candidate preset: `../preset.b10288-rocm-7.14-maxilp.sh`
