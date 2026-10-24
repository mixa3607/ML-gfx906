# Deepseek 4.1 requirements

- vision: on
- ctx limit: `192 * 1024`
- bit-exact only optimizations
- host mem limit: 192Gi
- model: `unsloth/DeepSeek-V4.1-Flash-1017-GGUF:UD-Q8_K_XL`
- dspark speculative: off
- gpu: 4x instinct mi50 32g

## image
Сейчас есть `docker.io/mixa3607/maya-gfx906:v1.1.26-rocm-10.1`. Можно использовать его или по согласованию собрать кастомные версии в приватный registry.

# Известные особенности по llama.cpp
- best cpu perf
  - prefill: 56 threads
  - decode: 48 threads
- best gpu perf
  - batch/ubatch: 2048
