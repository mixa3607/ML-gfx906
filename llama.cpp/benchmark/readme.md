# WIP

```bash
apt update && apt install tmux wget jq -y
python3 -m pip config set global.break-system-packages true
pip3 install yq
wget https://gist.githubusercontent.com/mixa3607/1e6d3ee7d87b018484cf80c7928b4c33/raw/.tmux.conf -O ~/.tmux.conf
curl https://gist.githubusercontent.com/mixa3607/e5b05e3da133a6ac5594717b3e0fe385/raw/bashrc-patcher.rb.sh | bash

wget https://github.com/Yoosu-L/llmapibenchmark/releases/download/v1.0.7/llmapibenchmark_linux_amd64.tar.gz
tar -xvfc llmapibenchmark_linux_amd64.tar.gz
./llmapibenchmark_linux_amd64 \
  --base-url http://127.0.0.1:8080/v1 --api-key none \
  --model $LLAMA_ARG_ALIAS \
  --concurrency 1 --max-tokens 512 --num-words 1000 \
  --format json
{
    "model_name": "gemma-3-27b",
    "input_tokens": 901,
    "output_tokens": 512,
    "latency": 0.6,
    "results": [
        {
            "concurrency": 1,
            "generation_speed": 8.14,
            "prompt_throughput": 136.66,
            "max_ttft": 25.75,
            "min_ttft": 25.75,
            "success_rate": 1
        }
    ]
}
```