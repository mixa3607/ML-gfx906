# vLLM benchmark
Run all commands in same pod. Actual for helm chart with [recipes](../recipes)

### Run
```bash
apt install tmux jq -y
pip3 install yq
wget https://gist.githubusercontent.com/mixa3607/1e6d3ee7d87b018484cf80c7928b4c33/raw/.tmux.conf -O ~/.tmux.conf
curl https://gist.githubusercontent.com/mixa3607/e5b05e3da133a6ac5594717b3e0fe385/raw/bashrc-patcher.rb.sh | bash

tmux

CONFIGS='
baseArgs: >
  --ignore-eos --num-warmups 4
benchmarks:
  ########### TG
  ## prefix-len 16
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16 --random-output-len 256
      --num-prompts 10 --max-concurrency=1
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16 --random-output-len 256
      --num-prompts=30 --max-concurrency=4
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16 --random-output-len 256
      --num-prompts 60 --max-concurrency 8
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16 --random-output-len 256
      --num-prompts 90 --max-concurrency 16
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16 --random-output-len 256
      --num-prompts 120 --max-concurrency 32
  
  ## prefix-len 4096
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 4096 --random-output-len 256
      --num-prompts 10 --max-concurrency=1
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 4096 --random-output-len 256
      --num-prompts=30 --max-concurrency=4
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 4096 --random-output-len 256
      --num-prompts 60 --max-concurrency 8
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 4096 --random-output-len 256
      --num-prompts 90 --max-concurrency 16
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 4096 --random-output-len 256
      --num-prompts 120 --max-concurrency 32

  ## prefix-len 16384
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16384 --random-output-len 256
      --num-prompts 10 --max-concurrency=1
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16384 --random-output-len 256
      --num-prompts=30 --max-concurrency=4
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16384 --random-output-len 256
      --num-prompts 60 --max-concurrency 8
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16384 --random-output-len 256
      --num-prompts 90 --max-concurrency 16
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 16384 --random-output-len 256
      --num-prompts 120 --max-concurrency 32
  
  ## prefix-len 32768
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 32768 --random-output-len 256
      --num-prompts 10 --max-concurrency=1
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 32768 --random-output-len 256
      --num-prompts=30 --max-concurrency=4
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 32768 --random-output-len 256
      --num-prompts 60 --max-concurrency 8
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 32768 --random-output-len 256
      --num-prompts 90 --max-concurrency 16
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 32768 --random-output-len 256
      --num-prompts 120 --max-concurrency 32
  
  ## prefix-len 65536
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 65536 --random-output-len 256
      --num-prompts 10 --max-concurrency=1
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 65536 --random-output-len 256
      --num-prompts=30 --max-concurrency=4
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 65536 --random-output-len 256
      --num-prompts 60 --max-concurrency 8
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 65536 --random-output-len 256
      --num-prompts 90 --max-concurrency 16
  - workload: tg
    args: >
      --dataset-name random
      --random-input-len 0 --random-prefix-len 65536 --random-output-len 256
      --num-prompts 120 --max-concurrency 32
  
  ########### PP
  - workload: pp
    args: >
      --dataset-name random 
      --random-input-len 8192 --random-prefix-len 0 --random-output-len 1 
      --num-prompts 10 --max-concurrency 1
  - workload: pp
    args: >
      --dataset-name random 
      --random-input-len 16384 --random-prefix-len 0 --random-output-len 1 
      --num-prompts 10 --max-concurrency 1
  - workload: pp
    args: >
      --dataset-name random 
      --random-input-len 32768 --random-prefix-len 0 --random-output-len 1 
      --num-prompts=10 --max-concurrency 1
  - workload: pp
    args: >
      --dataset-name random 
      --random-input-len 65536 --random-prefix-len 0 --random-output-len 1 
      --num-prompts 10 --max-concurrency 1
'

export POWER_CAP=$(rocm-smi -M --json | yq '.card0."Max Graphics Package Power (W)" | tonumber -0' -r)
export ROCM_VER="$(cat /opt/ROCM_VERSION_FULL)"
export TORCH_VER="$(pip show torch | sed -nE 's|^Version: (.+)|\1|p')"
export VISION_VER="$(pip show torchvision | sed -nE 's|^Version: (.+)|\1|p')"
export AUDIO_VER="$(pip show torchaudio | sed -nE 's|^Version: (.+)|\1|p')"
export VLLM_VER="$(pip show vllm | sed -nE 's|^Version: (.+)|\1|p')"
export TRITON_VER="$(pip show triton | sed -nE 's|^Version: (.+)|\1|p')"
export MODEL="$(cat vllm.yaml | yq '.model' -r)"
export BENCHMARK_AUTHOR="mixa3607"
export ABOUT="[recipe $RECIPE](./recipes/$RECIPE);"

for (( i=0; i<$(echo "$CONFIGS" | yq '.benchmarks | length'); i++ )); do
  BENCHMARK_NAME="$(echo "$CONFIGS" | yq ".benchmarks[$i].workload" -r)"
  BENCHMARK_ARGS="$(echo "$CONFIGS" | yq ".benchmarks[$i].args + \" \" + .baseArgs" -r | tr '\n' ' ')"

  echo "Run $BENCHMARK_NAME ($BENCHMARK_ARGS)"
  vllm bench serve $BENCHMARK_ARGS \
    --host 127.0.0.1 --model $MODEL --save-detailed --save-result \
    --metadata \
      metadata.workload="$BENCHMARK_NAME" \
      metadata.rocm_ver="$ROCM_VER" \
      metadata.torch_ver="$TORCH_VER" \
      metadata.vision_ver="$VISION_VER" \
      metadata.vllm_ver="$VLLM_VER" \
      metadata.triton_ver="$TRITON_VER" \
      metadata.image="$IMAGE_NAME" \
      metadata.about="$ABOUT" \
      metadata.benchmark_author="$BENCHMARK_AUTHOR" \
      metadata.power_cap="$POWER_CAP"
done
```

### Copy results from pod
```sh
kubectl exec -n ns-vllm pods/$(kubectl get pods -n ns-vllm -l app.kubernetes.io/instance=vllm -o jsonpath='{.items[].metadata.name}') -- bash -c 'cd /app/vllm/ && tar -zcvf - *.json' | tar -zxvf - -C results/
```

### Generate table
```sh
dotnet run --project ./ResultsConverter/ResultsConverter/ResultsConverter.csproj -- gen-table -i ./results/
```
