# VLLM GFX906
Used forks by https://github.com/nlzy:
- https://github.com/nlzy/vllm-gfx906
- https://github.com/nlzy/triton-gfx906

## Benchmarks

Methodology [benchmark](./benchmark/readme.md)

  date            | rocm  | torch              | vllm                        | triton            | TP | PwrCap | Model                                | Prompts | Threads | Duration         | RPS  | Output TPS | Total TPS | About                                    
 -----------------|-------|--------------------|-----------------------------|-------------------|----|--------|--------------------------------------|---------|---------|------------------|------|------------|-----------|----------------------------------------- 
  20251005-210513 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 150     | 4       | 00:20:10.3265325 | 0.12 | 58.77      | 186.03    | tested on rd450x 256G inside k3s in lxc  
  20251005-212640 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 125     | 3       | 00:20:00.2988691 | 0.10 | 48.18      | 154.96    | tested on rd450x 256G inside k3s in lxc  
  20251005-214604 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 100     | 2       | 00:18:05.4545212 | 0.09 | 41.81      | 136.23    | tested on rd450x 256G inside k3s in lxc  
  20251005-221837 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 75      | 1       | 00:27:37.0155547 | 0.05 | 21.18      | 67.61     | tested on rd450x 256G inside k3s in lxc  
  20251006-130816 | 6.3.3 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm633 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 75      | 1       | 00:19:16.0905731 | 0.06 | 19.44      | 86.00     | tested on rd450x 256G inside k3s in lxc  
  20251006-132621 | 6.3.3 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm633 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 100     | 2       | 00:17:29.1542989 | 0.10 | 41.52      | 139.21    | tested on rd450x 256G inside k3s in lxc  
  20251006-134724 | 6.3.3 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm633 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 125     | 3       | 00:20:06.5979349 | 0.10 | 48.32      | 154.54    | tested on rd450x 256G inside k3s in lxc  
  20251006-140759 | 6.3.3 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm633 | 3.3.0+git2b5c6ef9 | 2  | 150    | gaunernst/gemma-3-27b-it-qat-autoawq | 150     | 4       | 00:19:38.5187576 | 0.13 | 57.69      | 188.37    | tested on rd450x 256G inside k3s in lxc  
  20251007-162504 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 225    | gaunernst/gemma-3-27b-it-qat-autoawq | 75      | 1       | 00:19:22.7926510 | 0.06 | 20.08      | 86.25     | tested on rd450x 256G inside k3s in lxc  
  20251007-171239 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 225    | gaunernst/gemma-3-27b-it-qat-autoawq | 100     | 2       | 00:16:02.6107616 | 0.10 | 44.64      | 151.11    | tested on rd450x 256G inside k3s in lxc  
  20251007-173243 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 225    | gaunernst/gemma-3-27b-it-qat-autoawq | 125     | 3       | 00:19:21.7160991 | 0.11 | 50.35      | 160.67    | tested on rd450x 256G inside k3s in lxc  
  20251007-175203 | 6.4.4 | 2.7.1a0+gite2d141d | 0.1.dev1+gceec3eaf6.rocm644 | 3.3.0+git2b5c6ef9 | 2  | 225    | gaunernst/gemma-3-27b-it-qat-autoawq | 150     | 4       | 00:18:17.4322852 | 0.14 | 60.88      | 201.22    | tested on rd450x 256G inside k3s in lxc

## Run

## DockerHub images
> ghcr.io registry is deprecated. Use https://hub.docker.com/r/mixa3607/vllm-gfx906 instead

Tags:
- `jena` based on `rocm-6.3.3`. See more in `preset.setup-jena.sh`
- `ella` based on `rocm-6.4.4`. See more in `preset.setup-ella.sh` - multimodal requests throw exceptions
- ~~`eva` based on `rocm-7.0.0`. See more in `preset.setup-eva.sh`~~ error on build pytorch with llvm 20 in rocm 7.0.0

Recommend use `docker.io/mixa3607/vllm-gfx906:jena`

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



## Build
See build vars in `./env.sh`. You also may use presetis `./preset.setup-*.sh`. Exec `./build-and-push.vllm.sh`:
```bash
$ . preset.setup-ella.sh
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
