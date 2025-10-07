# vLLM benchmark
Run all commands in same pod

### 1. fill env vars
```sh
export VLLM_USE_V1=1                                        # vllm serve only. Required for gemma3
export VLLM_SLEEP_WHEN_IDLE=1                               # vllm serve only. Reduce CPU usage when vLLM is idle
export HUGGING_FACE_HUB_TOKEN=hf_XXXXXXXXXXXXXXXXXXXXXXX    # vllm serve only. HF api token
export POWER_CAP=225                                        # AMD GPU power cap
export TENSOR_PARALLELISM=2                                 # GPUs count. 1/2/4/8
export BENCHMARK_AUTHOR=mixa3607                            # author
export ABOUT="tested on rd450x 256G inside k3s in lxc"      # misc info
#export IMAGE_NAME="XXXX"                                   # set if not in env
```

### 2. Run vllm
```sh
# Run vllm with gemma3 27B in 4 bit quant
vllm serve gaunernst/gemma-3-27b-it-qat-autoawq --tensor-parallel-size $TENSOR_PARALLELISM --max-model-len 8K
```

### 3. Run benchmarks
```sh
# Set power cap and run benchmarks
amd-smi set --power-cap $POWER_CAP
echo -e '75 1\n100 2\n125 3\n150 4' | while read SETUP; do
  SETUP=($SETUP)
  vllm bench serve \
    --model gaunernst/gemma-3-27b-it-qat-autoawq \
    --host 127.0.0.1 \
    --num-prompts ${SETUP[0]} --max-concurrency ${SETUP[1]} \
    --dataset-name random --random-input-len 1024 --random-output-len 512 --random-range-ratio 0.1 \
    --save-detailed --save-result --metadata \
      metadata.rocm_ver="$(cat /opt/ROCM_VERSION_FULL)" \
      metadata.torch_ver="$(pip show torch | sed -nE 's|^Version: (.+)|\1|p')" \
      metadata.vision_ver="$(pip show torchvision | sed -nE 's|^Version: (.+)|\1|p')" \
      metadata.vllm_ver="$(pip show vllm | sed -nE 's|^Version: (.+)|\1|p')" \
      metadata.triton_ver="$(pip show triton | sed -nE 's|^Version: (.+)|\1|p')" \
      metadata.image="$IMAGE_NAME" \
      metadata.tensor_parallelism="$TENSOR_PARALLELISM" \
      metadata.about="$ABOUT" \
      metadata.benchmark_author="$BENCHMARK_AUTHOR" \
      metadata.tensor_parallelism="$TENSOR_PARALLELISM" \
      metadata.power_cap="$POWER_CAP"
done
```

### 4. Copy results from pod
```sh
kubectl exec -n ns-vllm pods/$(kubectl get pods -n ns-vllm -l app=vllm -o jsonpath='{.items[].metadata.name}') -- bash -c 'tar -zcvf - /app/vllm/*.json .' | tar -zxvf - -C results/
```

### 3. Generate table
```sh
dotnet run --project ./ResultsConverter/ResultsConverter/ResultsConverter.csproj -- gen-table -i ./results/
```
