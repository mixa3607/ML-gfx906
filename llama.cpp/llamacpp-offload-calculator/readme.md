# llama.cpp tesnsors offload calculator

## Conf

Supported config formats:
- json
- yaml
- env variables
- cmd args

Example:
### Base config `appsettings.yaml`
```yaml
# print -ot config for command line running
PrintCmdConfig: true
# print yaml for https://github.com/mixa3607/charts/tree/master/charts/llamacpp helm chart
PrintHelmCharConfig: true
# print size per tensor
PrintTensorsSize: false

# list from 'llama-server --list-devices' + CPU
Devices: # 1+ gpu and 1 cpu
  ROCm0: # name from llama.cpp output
    Id: 1 # used for ordering
    Type: GPU # GPU/CPU
    TotalSizeMb: 32768  # memory megabytes
    PciBus: 0000:01:00.0 # not used
  ROCm1:
    Id: 2
    Type: GPU
    TotalSizeMb: 32768
    PciBus: 0000:02:00.0
  CPU:
    Id: 3
    Type: CPU
    TotalSizeMb: 131072
    ReservedMemory: 0

# offloading rules
OffloadRules:
  ffn_gate_exps: # name
    Id: 1 # used for ordering
    Regex: '^blk\.\d+\.ffn_gate_exps.weight' # regex
    Priority: 10 # lower priority will be offloaded earlier
  ffn_up_exps:
    Id: 2
    Regex: '^blk\.\d+\.ffn_up_exps.weight'
    Priority: 20
  ffn_down_exps:
    Id: 3
    Regex: '^blk\.\d+\.ffn_down_exps.weight'
    Priority: 20
```

### Per model config `appsettings.noname-model.yaml`
```yaml
GgufFile: "/path/to/noname.gguf"

Devices:
  ROCm0:
    ReservedMemoryMb: 10240 # reserved memory for cache, ctx, etc
    #LayersPortion: 50 # layers percentage can be set manually
  ROCm1:
    ReservedMemoryMb: 10240
    #LayersPortion: 50
```

For the first start, you need to specify an increased ReservedMemoryMb with which llama.cpp will guaranteed to work.
```shell
$ cd ArkProjects.LlamaOffloadCalc
$ dotnet run -- -e noname-model
Reading /path/to/noname.gguf
Move blk.0.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.0.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.1.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.1.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.2.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.2.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.3.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.3.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.4.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.4.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.5.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.5.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.6.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.6.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.7.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.18.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.18.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.19.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.19.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.20.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.20.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.21.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.21.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.22.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.22.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.23.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.23.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.24.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.24.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.25.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
======= Device memory usage
ROCm0      32231 Mb of 32768 Mb (21991)
ROCm1      32231 Mb of 32768 Mb (21991)
CPU        16136 Mb of 131072 Mb (16136)

======= Tensors offload result
Offload ffn_gate_exps            (10) 0  (ROCm0 = 18, ROCm1 = 18, CPU = 0 ) of 36
Offload ffn_up_exps              (20) 0  (ROCm0 = 11, ROCm1 = 11, CPU = 14) of 36
Offload ffn_down_exps            (20) 0  (ROCm0 = 10, ROCm1 = 10, CPU = 16) of 36

======= Helm chart config
extraEnvVars:
  - name: LLAMA_ARG_MAIN_GPU
    value: '0'
  - name: LLAMA_ARG_TENSOR_SPLIT
    value: '18,18,0'

modelTensorsOverride:
  - name: CPU
    tensors:
    - blk.0.ffn_down_exps.weight
    - blk.0.ffn_up_exps.weight
    - blk.1.ffn_down_exps.weight
    - blk.1.ffn_up_exps.weight
    - blk.2.ffn_down_exps.weight
    - blk.2.ffn_up_exps.weight
    - blk.3.ffn_down_exps.weight
    - blk.3.ffn_up_exps.weight
    - blk.4.ffn_down_exps.weight
    - blk.4.ffn_up_exps.weight
    - blk.5.ffn_down_exps.weight
    - blk.5.ffn_up_exps.weight
    - blk.6.ffn_down_exps.weight
    - blk.6.ffn_up_exps.weight
    - blk.7.ffn_down_exps.weight
    - blk.18.ffn_down_exps.weight
    - blk.18.ffn_up_exps.weight
    - blk.19.ffn_down_exps.weight
    - blk.19.ffn_up_exps.weight
    - blk.20.ffn_down_exps.weight
    - blk.20.ffn_up_exps.weight
    - blk.21.ffn_down_exps.weight
    - blk.21.ffn_up_exps.weight
    - blk.22.ffn_down_exps.weight
    - blk.22.ffn_up_exps.weight
    - blk.23.ffn_down_exps.weight
    - blk.23.ffn_up_exps.weight
    - blk.24.ffn_down_exps.weight
    - blk.24.ffn_up_exps.weight
    - blk.25.ffn_down_exps.weight

======= CMD config
--main-gpu 0 --tensor-split "18,18,0" --override-tensor "(blk.0.ffn_down_exps.weight|blk.0.ffn_up_exps.weight|blk.1.ffn_down_exps.weight|blk.1.ffn_up_exps.weight|blk.2.ffn_down_exps.weight|blk.2.ffn_up_exps.weight|blk.3.ffn_down_exps.weight|blk.3.ffn_up_exps.weight|blk.4.ffn_down_exps.weight|blk.4.ffn_up_exps.weight|blk.5.ffn_down_exps.weight|blk.5.ffn_up_exps.weight|blk.6.ffn_down_exps.weight|blk.6.ffn_up_exps.weight|blk.7.ffn_down_exps.weight|blk.18.ffn_down_exps.weight|blk.18.ffn_up_exps.weight|blk.19.ffn_down_exps.weight|blk.19.ffn_up_exps.weight|blk.20.ffn_down_exps.weight|blk.20.ffn_up_exps.weight|blk.21.ffn_down_exps.weight|blk.21.ffn_up_exps.weight|blk.22.ffn_down_exps.weight|blk.22.ffn_up_exps.weight|blk.23.ffn_down_exps.weight|blk.23.ffn_up_exps.weight|blk.24.ffn_down_exps.weight|blk.24.ffn_up_exps.weight|blk.25.ffn_down_exps.weight)=CPU"
```

```
┌┌┤ Memory Usage ├──────────────────────────────────────────────────────────┐ │  ┌┤ Memory Usage ├──────────────────────────────────────────────────────────┐
││ VRAM: [     30393 / 32752 MiB     ]  GTT: [        14 / 48256 MiB     ]  │ │  │ VRAM: [     31079 / 32752 MiB     ]  GTT: [        14 / 48256 MiB     ]  │ 
└└──────────────────────────────────────────────────────────────────────────┘ │  └──────────────────────────────────────────────────────────────────────────┘
```

After the stress test, you can reduce ReservedMemoryMb by the amount of free memory from the first run.

```yaml
GgufFile: "/path/to/noname.gguf"
Devices:
  ROCm0:
    ReservedMemoryMb: 9300
  ROCm1:
    ReservedMemoryMb: 8500
```

```shell
$ cd ArkProjects.LlamaOffloadCalc
$ dotnet run -- -e noname-model
Reading /path/to/noname.gguf
Move blk.0.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.0.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.1.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.1.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.2.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.2.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.3.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.3.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.4.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.4.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.5.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.5.ffn_up_exps.weight  (537 Mb) from ROCm0 to CPU
Move blk.6.ffn_down_exps.weight (537 Mb) from ROCm0 to CPU
Move blk.18.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.18.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.19.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.19.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.20.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.20.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.21.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.21.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.22.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.22.ffn_up_exps.weight (537 Mb) from ROCm1 to CPU
Move blk.23.ffn_down_exps.weight (537 Mb) from ROCm1 to CPU
======= Device memory usage
ROCm0      32366 Mb of 32768 Mb (23066)
ROCm1      32642 Mb of 32768 Mb (24142)
CPU        12909 Mb of 131072 Mb (12909)

======= Tensors offload result
Offload ffn_gate_exps            (10) 0  (ROCm0 = 18, ROCm1 = 18, CPU = 0 ) of 36
Offload ffn_up_exps              (20) 0  (ROCm0 = 12, ROCm1 = 13, CPU = 11) of 36
Offload ffn_down_exps            (20) 0  (ROCm0 = 11, ROCm1 = 12, CPU = 13) of 36

======= Helm chart config
extraEnvVars:
  - name: LLAMA_ARG_MAIN_GPU
    value: '0'
  - name: LLAMA_ARG_TENSOR_SPLIT
    value: '18,18,0'

modelTensorsOverride:
  - name: CPU
    tensors:
    - blk.0.ffn_down_exps.weight
    - blk.0.ffn_up_exps.weight
    - blk.1.ffn_down_exps.weight
    - blk.1.ffn_up_exps.weight
    - blk.2.ffn_down_exps.weight
    - blk.2.ffn_up_exps.weight
    - blk.3.ffn_down_exps.weight
    - blk.3.ffn_up_exps.weight
    - blk.4.ffn_down_exps.weight
    - blk.4.ffn_up_exps.weight
    - blk.5.ffn_down_exps.weight
    - blk.5.ffn_up_exps.weight
    - blk.6.ffn_down_exps.weight
    - blk.18.ffn_down_exps.weight
    - blk.18.ffn_up_exps.weight
    - blk.19.ffn_down_exps.weight
    - blk.19.ffn_up_exps.weight
    - blk.20.ffn_down_exps.weight
    - blk.20.ffn_up_exps.weight
    - blk.21.ffn_down_exps.weight
    - blk.21.ffn_up_exps.weight
    - blk.22.ffn_down_exps.weight
    - blk.22.ffn_up_exps.weight
    - blk.23.ffn_down_exps.weight

======= CMD config
--main-gpu 0 --tensor-split "18,18,0" --override-tensor "(blk.0.ffn_down_exps.weight|blk.0.ffn_up_exps.weight|blk.1.ffn_down_exps.weight|blk.1.ffn_up_exps.weight|blk.2.ffn_down_exps.weight|blk.2.ffn_up_exps.weight|blk.3.ffn_down_exps.weight|blk.3.ffn_up_exps.weight|blk.4.ffn_down_exps.weight|blk.4.ffn_up_exps.weight|blk.5.ffn_down_exps.weight|blk.5.ffn_up_exps.weight|blk.6.ffn_down_exps.weight|blk.18.ffn_down_exps.weight|blk.18.ffn_up_exps.weight|blk.19.ffn_down_exps.weight|blk.19.ffn_up_exps.weight|blk.20.ffn_down_exps.weight|blk.20.ffn_up_exps.weight|blk.21.ffn_down_exps.weight|blk.21.ffn_up_exps.weight|blk.22.ffn_down_exps.weight|blk.22.ffn_up_exps.weight|blk.23.ffn_down_exps.weight)=CPU"
```

```
┌┌┤ Memory Usage ├──────────────────────────────────────────────────────────┐ │  ┌┤ Memory Usage ├──────────────────────────────────────────────────────────┐
││ VRAM: [     32545 / 32752 MiB     ]  GTT: [        14 / 48256 MiB     ]  │ │  │ VRAM: [     32155 / 32752 MiB     ]  GTT: [        14 / 48256 MiB     ]  │ 
└└──────────────────────────────────────────────────────────────────────────┘ │  └──────────────────────────────────────────────────────────────────────────┘

prompt eval time =   57715.98 ms /  8777 tokens (    6.58 ms per token,   152.07 tokens per second)
       eval time =   66072.62 ms /   878 tokens (   75.25 ms per token,    13.29 tokens per second)
      total time =  123788.60 ms /  9655 tokens
```
