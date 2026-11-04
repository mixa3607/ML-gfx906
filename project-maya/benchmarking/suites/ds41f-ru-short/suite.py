"""DeepSeek-V4.1-Flash, thinking off, warm-cache single-request throughput."""

# Maya chat encoder: v1.1.38, cf6472cc84489765791ad97bb55b395e8f442088.
CORPUS = 'ru-prose'
SEED = 20261024
TG = 256
WARMUP_PP = [2048] * 8
MEASUREMENT_PP = [2048, 4096, 8192, 16384, 32768]
ASSISTANT_SUFFIX = '<｜Assistant｜></think>'
RENDER_KWARGS = {'reasoning_effort': 'none'}
