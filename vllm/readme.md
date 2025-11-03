# VLLM GFX906
Used forks by https://github.com/nlzy:
- https://github.com/nlzy/vllm-gfx906
- https://github.com/nlzy/triton-gfx906

## Benchmarks

Methodology [benchmark](./benchmark/readme.md)

  date            | rocm  | vllm                        | PwrCap | Model                                   | Prompts | Threads | Duration         | RPM   | Output TPS | Total TPS | About                                                                                                                     
 -----------------|-------|-----------------------------|--------|-----------------------------------------|---------|---------|------------------|-------|------------|-----------|-------------------------------------------------------------------------------------------------------------------------- 
  20251005-210513 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 150     | 4       | 00:20:10.3265325 | 7.44  | 58.77      | 186.03    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251005-212640 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 125     | 3       | 00:20:00.2988691 | 6.25  | 48.18      | 154.96    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251005-214604 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 100     | 2       | 00:18:05.4545212 | 5.53  | 41.81      | 136.23    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251005-221837 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 75      | 1       | 00:27:37.0155547 | 2.72  | 21.18      | 67.61     | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251006-130816 | 6.3.3 | 0.1.dev1+gceec3eaf6.rocm633 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 75      | 1       | 00:19:16.0905731 | 3.89  | 19.44      | 86.00     | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251006-132621 | 6.3.3 | 0.1.dev1+gceec3eaf6.rocm633 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 100     | 2       | 00:17:29.1542989 | 5.72  | 41.52      | 139.21    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251006-134724 | 6.3.3 | 0.1.dev1+gceec3eaf6.rocm633 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 125     | 3       | 00:20:06.5979349 | 6.22  | 48.32      | 154.54    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251006-140759 | 6.3.3 | 0.1.dev1+gceec3eaf6.rocm633 | 150    | gaunernst/gemma-3-27b-it-qat-autoawq    | 150     | 4       | 00:19:38.5187576 | 7.64  | 57.69      | 188.37    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251007-162504 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 75      | 1       | 00:19:22.7926510 | 3.87  | 20.08      | 86.25     | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251007-171239 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 100     | 2       | 00:16:02.6107616 | 6.23  | 44.64      | 151.11    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251007-173243 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 125     | 3       | 00:19:21.7160991 | 6.46  | 50.35      | 160.67    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251007-175203 | 6.4.4 | 0.1.dev1+gceec3eaf6.rocm644 | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 150     | 4       | 00:18:17.4322852 | 8.20  | 60.88      | 201.22    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251012-111624 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 75      | 1       | 00:21:05.0039699 | 3.56  | 16.07      | 76.89     | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251012-112842 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 100     | 2       | 00:11:41.9394741 | 8.55  | 35.56      | 181.57    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251012-114201 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 125     | 3       | 00:12:43.8522526 | 9.82  | 41.50      | 209.29    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251012-115501 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 150     | 4       | 00:12:24.0047521 | 12.10 | 48.33      | 255.35    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251012-121023 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 200     | 8       | 00:13:31.6286220 | 14.79 | 54.78      | 308.18    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251012-201017 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 100     | 16      | 00:07:22.8462734 | 13.55 | 54.01      | 285.44    | tested on rd450x 256G inside k3s in lxc                                                                                   
  20251013-140107 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 75      | 1       | 00:20:08.6821350 | 3.72  | 15.66      | 79.31     | TdcLimitGfx=150                                                                                                           
  20251013-141355 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 100     | 2       | 00:12:11.5680303 | 8.20  | 34.12      | 174.22    | TdcLimitGfx=150                                                                                                           
  20251013-142754 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 125     | 3       | 00:13:21.9331666 | 9.35  | 39.53      | 199.35    | TdcLimitGfx=150                                                                                                           
  20251013-144145 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 150     | 4       | 00:13:13.4142282 | 11.34 | 46.02      | 240.14    | TdcLimitGfx=150                                                                                                           
  20251103-151641 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 75      | 1       | 00:22:18.8232647 | 3.36  | 26.62      | 84.01     | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251103-153740 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 100     | 2       | 00:20:18.2074826 | 4.93  | 41.44      | 125.57    | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251103-155746 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 125     | 3       | 00:19:27.3167974 | 6.42  | 51.30      | 160.78    | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251103-161758 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-32B-Instruct-AWQ     | 150     | 4       | 00:19:32.9857392 | 7.67  | 61.73      | 192.75    | [recipe QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-32B-Instruct-AWQ-001.yaml);          
  20251103-164840 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 75      | 1       | 00:14:23.5029942 | 5.21  | 39.29      | 128.28    | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251103-170229 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 100     | 2       | 00:13:27.9544295 | 7.43  | 46.25      | 173.11    | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251103-172025 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 125     | 3       | 00:17:20.9837457 | 7.20  | 47.80      | 170.56    | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251103-173846 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | QuantTrio/Qwen3-VL-30B-A3B-Instruct-AWQ | 150     | 4       | 00:17:58.6149264 | 8.34  | 60.85      | 203.33    | [recipe QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml](./recipes/QuantTrio--Qwen3-VL-30B-A3B-Instruct-AWQ-001.yaml);  
  20251103-182144 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 75      | 1       | 00:27:26.4145022 | 2.73  | 16.60      | 63.34     | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251103-183642 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 100     | 2       | 00:14:05.7216656 | 7.09  | 39.36      | 160.55    | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251103-185115 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 125     | 3       | 00:14:07.2101350 | 8.85  | 45.16      | 196.44    | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);        
  20251103-190644 | 6.3.3 | 0.11.0+gfx906.rocm633       | 225    | gaunernst/gemma-3-27b-it-qat-autoawq    | 150     | 4       | 00:14:38.8395358 | 10.24 | 53.78      | 229.03    | [recipe gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml](./recipes/gaunernst--gemma-3-27b-it-qat-autoawq-001.yaml);   

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
