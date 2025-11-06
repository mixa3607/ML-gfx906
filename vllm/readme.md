# VLLM GFX906
Used forks:
- https://github.com/tomylin890/vllm-gfx906
- https://github.com/nlzy/vllm-gfx906
- https://github.com/nlzy/triton-gfx906

## Benchmarks

- `AVG in` - average input tokens
- `AVG out` - average output tokens
- `Duration` - total test duration
- `RPM` - requests/minute
- `TG` - Output token throughput (tok/s)
- `Total TPS` - Total Token throughput (tok/s)

Methodology [benchmark](./benchmark/readme.md); [Google sheets](https://docs.google.com/spreadsheets/d/1VpBHm-9nGtlmtZd6eqXVJw3eN4QvlvAO_qkhmsFuiSk/edit?usp=sharing)

  date            | rocm  | vllm                        | PwrCap | Model                                   | Prompts | Threads | AVG in | AVG out | Duration | RPM | TG     | Total TPS | Workload | About                                                                                                                     
 -----------------|-------|-----------------------------|--------|-----------------------------------------|---------|---------|--------|---------|----------|-----|--------|-----------|----------|-------------------------------------------------------------------------------------------------------------------------- 
  20251105-144515 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 10      | 1       | 16     | 256     | 00:02:13 | -   | 19.11  | -         | tg       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-144716 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 30      | 4       | 16     | 256     | 00:01:15 | -   | 101.17 | -         | tg       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-145137 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 10      | 1       | 4096   | 256     | 00:02:33 | -   | 16.67  | -         | tg       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-145439 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 30      | 4       | 4096   | 256     | 00:01:59 | -   | 64.19  | -         | tg       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-150110 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 10      | 1       | 16384  | 256     | 00:03:43 | -   | 11.43  | -         | tg       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-150719 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 30      | 4       | 16384  | 256     | 00:04:15 | -   | 30.01  | -         | tg       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-151050 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 10      | 1       | 8191   | 1       | 00:02:48 | -   | -      | 485.95    | pp       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-151759 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 10      | 1       | 16383  | 1       | 00:06:05 | -   | -      | 448.85    | pp       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-152922 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 10      | 1       | 24575  | 1       | 00:09:52 | -   | -      | 415.13    | pp       | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251105-154326 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 16     | 256     | 00:01:19 | -   | 32.28  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-154524 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 30      | 4       | 16     | 256     | 00:01:19 | -   | 96.17  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-154816 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 4096   | 256     | 00:01:32 | -   | 27.79  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-155105 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 30      | 4       | 4096   | 256     | 00:01:51 | -   | 68.73  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-155624 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 16384  | 256     | 00:02:15 | -   | 18.95  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-160227 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 30      | 4       | 16384  | 256     | 00:03:24 | -   | 37.55  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-160855 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 8192   | 1       | 00:05:29 | -   | -      | 248.37    | pp       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-162635 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 16384  | 1       | 00:16:02 | -   | -      | 170.15    | pp       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251105-170346 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 24576  | 1       | 00:33:06 | -   | -      | 123.73    | pp       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251106-050708 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 16     | 256     | 00:00:59 | -   | 43.14  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-050943 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 30      | 4       | 16     | 256     | 00:01:53 | -   | 67.67  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-051147 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 4096   | 256     | 00:01:07 | -   | 38.02  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-051408 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 30      | 4       | 4096   | 256     | 00:01:37 | -   | 79.13  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-051712 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 16384  | 256     | 00:01:33 | -   | 27.27  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-052047 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 30      | 4       | 16384  | 256     | 00:02:21 | -   | 54.11  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-052251 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 8192   | 1       | 00:01:32 | -   | -      | 884.73    | pp       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-052610 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 16384  | 1       | 00:02:38 | -   | -      | 1,032.15  | pp       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-053043 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 24576  | 1       | 00:03:45 | -   | -      | 1,091.46  | pp       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-002.yaml);  
  20251106-070949 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 16     | 256     | 00:00:57 | -   | 44.21  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-071218 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 30      | 4       | 16     | 256     | 00:01:48 | -   | 70.73  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-071424 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 4096   | 256     | 00:01:07 | -   | 37.97  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-071642 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 30      | 4       | 4096   | 256     | 00:01:35 | -   | 80.79  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-071959 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 16384  | 256     | 00:01:34 | -   | 27.22  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-072349 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 30      | 4       | 16384  | 256     | 00:02:25 | -   | 52.80  | -         | tg       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-072626 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 8192   | 1       | 00:02:01 | -   | -      | 673.24    | pp       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-073121 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 16384  | 1       | 00:04:04 | -   | -      | 669.26    | pp       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-073837 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 10      | 1       | 24576  | 1       | 00:06:11 | -   | -      | 661.96    | pp       | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251106-075033 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 16     | 256     | 00:01:20 | -   | 31.92  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-075232 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 30      | 4       | 16     | 256     | 00:01:20 | -   | 95.79  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-075520 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 4096   | 256     | 00:01:31 | -   | 27.84  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-075806 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 30      | 4       | 4096   | 256     | 00:01:51 | -   | 69.05  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-080247 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 16384  | 256     | 00:02:13 | -   | 19.12  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-080809 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 30      | 4       | 16384  | 256     | 00:03:21 | -   | 38.14  | -         | tg       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-081254 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 8192   | 1       | 00:03:57 | -   | -      | 345.61    | pp       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-082412 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 16384  | 1       | 00:10:09 | -   | -      | 268.76    | pp       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          
  20251106-084710 | 6.3.3 | 0.1.dev1+ga1db3d80a.rocm633 | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 10      | 1       | 24576  | 1       | 00:20:18 | -   | -      | 201.70    | pp       | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-002.yaml);          

## Run

## DockerHub images
> ghcr.io registry is deprecated. Use https://hub.docker.com/r/mixa3607/vllm-gfx906 instead

Vers compatibility table:
| ROCm  | PyTorch | vLLM   | triton | model                                | text | images | misc |
| ----- | ------- | ------ | ------ | ------------------------------------ | ---- | ------ | ---- |
| 6.3.3 | 2.7.1   | 0.10.2 | 3.3.0  | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ✅️ | ok |
| 6.4.4 | 2.7.1   | 0.10.2 | 3.3.0  | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ⛔ | requests with images throw exception |
| 6.3.3 | 2.8.0   | 0.11.0 | 3.4.0  | gaunernst/gemma-3-27b-it-qat-autoawq | ✅️ | ✅️ | ok |
| 6.3.3 | 2.8.0   | 0.11.0 | 3.4.0  | QuantTrio/Qwen3-VL-32B-Instruct-AWQ  | ✅️ | ✅️ | ok |
| 6.4.4 | 2.8.0   | 0.11.0 | 3.4.0  | gaunernst/gemma-3-27b-it-qat-autoawq | ⛔ | ⛔ | all requests throw exception |

Recommend use `docker.io/mixa3607/vllm-gfx906:0.11.0-rocm-6.3.3`

### Docker
Basics from amd https://github.com/ROCm/vllm/blob/main/docs/deployment/docker.md

### Kubernetes
```yaml
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vllm-models
  namespace: ns-vllm
spec:
  accessModes:
    - ReadWriteOnce
  volumeMode: Filesystem
  storageClassName: nfs-ssd-1
  resources:
    requests:
      storage: 64Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm
  namespace: ns-vllm
  labels:
    app: vllm
spec:
  strategy:
    type: Recreate
  replicas: 1
  selector:
    matchLabels:
      app: vllm
  template:
    metadata:
      labels:
        app: vllm
    spec:
      volumes:
        - name: models-volume
          persistentVolumeClaim:
            claimName: vllm-models
        - name: dev-kfd
          hostPath:
            path: /dev/kfd
        - name: dev-dri
          hostPath:
            path: /dev/dri
        - name: shm
          emptyDir:
            medium: Memory
            sizeLimit: 32G
      containers:
        - name: vllm
          image: docker.io/mixa3607/vllm-gfx906:ella
          imagePullPolicy: Always
          securityContext:
            privileged: true
            runAsNonRoot: false
            runAsGroup: 0
            runAsUser: 0
            seccompProfile:
              type: Unconfined
            capabilities:
              add:
                - SYS_PTRACE
          command: [ "/bin/bash", "-c" ]
          args:
            #- "while true; do sleep 1s; done;"
            - |
              export VLLM_USE_V1=1
              export HUGGING_FACE_HUB_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXX
              exec vllm serve gaunernst/gemma-3-27b-it-qat-autoawq --tensor-parallel-size 2 --max-model-len 16K
          ports:
            - containerPort: 8000
          resources:
            limits:
              memory: 64G
            requests:
              cpu: "6"
              memory: 6G
          volumeMounts:
            - mountPath: /root/.cache/huggingface
              name: models-volume
            - name: shm
              mountPath: /dev/shm
            - name: dev-kfd
              mountPath: /dev/kfd
            - name: dev-dri
              mountPath: /dev/dri
```

## Gemma3 AWQ patch for 0.11.0
```bash
echo '
--- /usr/local/lib/python3.12/dist-packages/vllm/config/model.py        2025-10-12 13:22:53.000000000 +0000
+++ /usr/local/lib/python3.12/dist-packages/vllm/config/model.py        2025-10-12 13:59:26.271776131 +0000
@@ -1586,6 +1586,7 @@
     "plamo2": "Numerical instability. Please use bfloat16 or float32 instead.",
     "glm4": "Numerical instability. Please use bfloat16 or float32 instead.",
 }
+_FLOAT16_NOT_SUPPORTED_MODELS = {}


 def _is_valid_dtype(model_type: str, dtype: torch.dtype):' | patch -d/ -p0

echo '
--- /usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/gemma3.py
+++ /usr/local/lib/python3.12/dist-packages/vllm/model_executor/models/gemma3.py
@@ -329,6 +329,9 @@ class Gemma3DecoderLayer(nn.Module):
         residual: Optional[torch.Tensor],
         **kwargs,
     ) -> tuple[torch.Tensor, torch.Tensor]:
+        # https://github.com/huggingface/transformers/pull/36832
+        if hidden_states.dtype == torch.float16:
+            hidden_states = hidden_states.clamp_(-65504, 65504)
         if residual is None:
             residual = hidden_states
             hidden_states = self.input_layernorm(hidden_states)
@@ -341,11 +344,15 @@ class Gemma3DecoderLayer(nn.Module):
             **kwargs,
         )
         hidden_states = self.post_attention_layernorm(hidden_states)
+        if hidden_states.dtype == torch.float16:
+            hidden_states = hidden_states.clamp_(-65504, 65504)

         hidden_states, residual = self.pre_feedforward_layernorm(
             hidden_states, residual)
         hidden_states = self.mlp(hidden_states)
         hidden_states = self.post_feedforward_layernorm(hidden_states)
+        if hidden_states.dtype == torch.float16:
+            hidden_states = hidden_states.clamp_(-65504, 65504)
         return hidden_states, residual


@@ -552,4 +559,4 @@ class Gemma3ForCausalLM(nn.Module, SupportsLoRA, SupportsPP):
             skip_prefixes=(["lm_head."]
                            if self.config.tie_word_embeddings else None),
         )
-        return loader.load_weights(weights)
+        return loader.load_weights(weights)' | patch -d/ -p0
```


## Build
See build vars in `./env.sh`. You also may use presetis `./preset.*.sh`. Exec `./build-and-push.vllm.sh`:
```bash
$ . preset.0.11.0-rocm-6.3.3.sh
$ ./build-and-push.vllm.sh
~/REPOS/mixa3607/llama.cpp-gfx906/rocm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/llama.cpp ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/comfyui ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/vllm ~/REPOS/mixa3607/llama.cpp-gfx906/rocm
~/REPOS/mixa3607/llama.cpp-gfx906/rocm
#0 building with "remote" instance using remote driver
#...............
#14 DONE 583.8s
```
