# VLLM GFX906
Used forks by https://github.com/nlzy:
- https://github.com/nlzy/vllm-gfx906
- https://github.com/nlzy/triton-gfx906

## Benchmarks
```bash
$ amd-smi set --power-cap 190
$ vllm bench serve --model gaunernst/gemma-3-27b-it-qat-autoawq --host 127.0.0.1 --num-prompts 10 --max-concurrency 1 --dataset-name random --random-input-len 6144 --random-output-len 16
============ Serving Benchmark Result ============
Successful requests:                     10
Maximum request concurrency:             1
Benchmark duration (s):                  148.72
Total input tokens:                      61430
Total generated tokens:                  104
Request throughput (req/s):              0.07
Output token throughput (tok/s):         0.70
Total Token throughput (tok/s):          413.75
---------------Time to First Token----------------
Mean TTFT (ms):                          14391.39
Median TTFT (ms):                        16005.28
P99 TTFT (ms):                           16044.94
-----Time per Output Token (excl. 1st token)------
Mean TPOT (ms):                          51.44
Median TPOT (ms):                        51.31
P99 TPOT (ms):                           52.42
---------------Inter-token Latency----------------
Mean ITL (ms):                           51.09
Median ITL (ms):                         50.92
P99 ITL (ms):                            52.98
==================================================

$ amd-smi set --power-cap 190
$ vllm bench serve --model gaunernst/gemma-3-27b-it-qat-autoawq --host 127.0.0.1 --num-prompts 20 --max-concurrency 2 --dataset-name random --random-input-len 6144 --random-output-len 16
============ Serving Benchmark Result ============
Successful requests:                     20
Maximum request concurrency:             2
Benchmark duration (s):                  307.73
Total input tokens:                      122860
Total generated tokens:                  296
Request throughput (req/s):              0.06
Output token throughput (tok/s):         0.96
Total Token throughput (tok/s):          400.21
---------------Time to First Token----------------
Mean TTFT (ms):                          16477.15
Median TTFT (ms):                        15875.39
P99 TTFT (ms):                           29815.70
-----Time per Output Token (excl. 1st token)------
Mean TPOT (ms):                          933.92
Median TPOT (ms):                        1081.86
P99 TPOT (ms):                           1963.74
---------------Inter-token Latency----------------
Mean ITL (ms):                           1010.66
Median ITL (ms):                         50.86
P99 ITL (ms):                            6172.13
==================================================
```

## Run
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
      annotations:
        prometheus.io/scrape: 'true'
    spec:
      tolerations:
        - key: feature.node.kubernetes.io/amd-gpu
          operator: Equal
          value: 'true'
          effect: NoExecute
      nodeSelector:
        feature.node.kubernetes.io/amd-gpu: 'true'
      imagePullSecrets:
        - name: harbor-registry-pull-secret
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
      hostNetwork: false
      hostIPC: false
      containers:
        - name: vllm
          #image: docker.io/nalanzeyu/vllm-gfx906:latest
          image: registry.arkprojects.space/apps/vllm/vllm:eb009084a-triton-v3.3.0gfx906-rocm-6.3.3
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

## Build
Export env vars or use defaults defined in `./env.sh`:
- `VLLM_ROCM_VERSION` to required ROCm ver
- `PATCHED_VLLM_REGISTRY` to your regisry addr

Exec `./build-and-push.vllm.sh`
```bash
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