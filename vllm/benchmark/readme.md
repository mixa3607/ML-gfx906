# vLLM benchmark
Run all commands in same pod. Actual for helm chart with [recipes](../recipes)

### Run
```bash
apt install tmux wget jq -y
pip3 install yq
wget https://gist.githubusercontent.com/mixa3607/1e6d3ee7d87b018484cf80c7928b4c33/raw/.tmux.conf -O ~/.tmux.conf
curl https://gist.githubusercontent.com/mixa3607/e5b05e3da133a6ac5594717b3e0fe385/raw/bashrc-patcher.rb.sh | bash
curl 'https://github.com/kimbochen/vllm/raw/9a98dd2412feee155f6e4e44d7a9506dd5c3de9a/vllm/benchmarks/serve.py' -L > /usr/local/lib/python3.12/dist-packages/vllm/benchmarks/serve.py

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

tmux

CONFIGS='
########### TG
- workload: "tg;"
  args: >
    --dataset-name random 
    --random-input-len 0 --random-prefix-len 16 --random-output-len 256 
    --num-prompts=10 --max-concurrency=1
- workload: "tg;"
  args: >
    --dataset-name random 
    --random-input-len 0 --random-prefix-len 16 --random-output-len 256 
    --num-prompts=30 --max-concurrency=4

- workload: "tg;"
  args: >
    --dataset-name random 
    --random-input-len 0 --random-prefix-len 4096 --random-output-len 256 
    --num-prompts=10 --max-concurrency=1
- workload: "tg;"
  args: >
    --dataset-name random 
    --random-input-len 0 --random-prefix-len 4096 --random-output-len 256 
    --num-prompts=30 --max-concurrency=4

- workload: "tg;"
  args: >
    --dataset-name random 
    --random-input-len 0 --random-prefix-len 16384 --random-output-len 256 
    --num-prompts=10 --max-concurrency=1
- workload: "tg;"
  args: >
    --dataset-name random 
    --random-input-len 0 --random-prefix-len 16384 --random-output-len 256 
    --num-prompts=30 --max-concurrency=4

########### PP
- workload: "pp;"
  args: >
    --dataset-name random 
    --random-input-len 8192 --random-prefix-len 0 --random-output-len 1 
    --num-prompts=10 --max-concurrency=1
- workload: "pp;"
  args: >
    --dataset-name random 
    --random-input-len 16384 --random-prefix-len 0 --random-output-len 1 
    --num-prompts=10 --max-concurrency=1
- workload: "pp;"
  args: >
    --dataset-name random 
    --random-input-len 24576 --random-prefix-len 0 --random-output-len 1 
    --num-prompts=10 --max-concurrency=1

########### MIXED
#- workload: "mixed;"
#  args: >
#    --dataset-name random --random-range-ratio 0.1
#    --random-input-len 8192 --random-prefix-len 0 --random-output-len 512
#    --num-prompts=60 --max-concurrency=1
#- workload: "mixed;"
#  args: >
#    --dataset-name random --random-range-ratio 0.1
#    --random-input-len 8192 --random-prefix-len 0 --random-output-len 512
#    --num-prompts=60 --max-concurrency=2
#- workload: "mixed;"
#  args: >
#    --dataset-name random --random-range-ratio 0.1
#    --random-input-len 8192 --random-prefix-len 0 --random-output-len 512
#    --num-prompts=60 --max-concurrency=4
'

for (( i=0; i<$(echo "$CONFIGS" | yq '. | length'); i++ )); do
  WORKLOAD_NAME="$(echo "$CONFIGS" | yq ".[$i].workload" -r)"
  echo "Run $WORKLOAD_NAME"
  vllm bench serve $(echo "$CONFIGS" | yq ".[$i].args" -r | tr -d '\n') \
  --host 127.0.0.1 \
  --model $MODEL --ignore-eos --num-warmups 4 \
  --save-detailed --save-result --metadata \
    metadata.workload="$WORKLOAD_NAME" \
    metadata.rocm_ver="$ROCM_VER" metadata.torch_ver="$TORCH_VER" metadata.vision_ver="$VISION_VER" metadata.vllm_ver="$VLLM_VER" \
    metadata.triton_ver="$TRITON_VER" metadata.image="$IMAGE_NAME" \
    metadata.about="$ABOUT" metadata.benchmark_author="$BENCHMARK_AUTHOR" metadata.power_cap="$POWER_CAP"
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
