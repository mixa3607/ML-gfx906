# FreeToken on MI50 / gfx906

Experimental ROCm deployment of [FlashML-org/FreeToken](https://github.com/FlashML-org/FreeToken).

## Stack

- FreeToken: `11c1adb88f58a1a9d0ae47b8cd70ca0c7a4793c4`.
- PyTorch: `2.13.0+gfx906.20260802001858`, ROCm `7.14.60850`.
- Triton: `3.6.0`, [gfx906 fork](https://github.com/Dao-AILab/triton-gfx906), commit `82957a511217fdfefea434c05ee2c21aa78622ac`.
- Test checkpoint: `Qwen/Qwen3-0.6B`, revision `c1899de289a04d12100db370d81485cdf75e47ca`, downloaded into the `apps-ml/shared-hf-cache` PVC.
- Image: `registry.arkprojects.space/apps/freetoken-gfx906:11c1adb-rocm7.14-torch2.13`.
- Tested image digest: `sha256:2db30eb49691f3a5a841b3a1727a9c732b961647cb45df5c9c220fdd71c0df2a`.

Upstream currently requires PyTorch 2.14. The build adjusts its package metadata for the existing gfx906 PyTorch 2.13 image; this is a local compatibility build, not an upstream-supported configuration. CUDA-only optional accelerator packages are not installed. `amdsmi` is removed: this version returns zero MI50 handles, causing PyTorch to report no devices before HIP initialization. HIP enumeration correctly discovers all four cards without it.

`PYTORCH_ALLOC_CONF=expandable_segments:False` is required: MI50 does not support the VMM allocation path automatically enabled by FreeToken, which otherwise fails with a misleading out-of-memory error on the first small allocation.

## Build

Source repositories must already be checked out at the revisions above under `~/REPOS`:

```bash
bash freetoken/build-and-push.sh
```

Override `FREETOKEN_SOURCE`, `TRITON_SOURCE`, or `IMAGE` as needed. Uses the selected Docker Buildx builder and pushes only to the configured private registry.

The first Triton build downloads its pinned LLVM/MLIR SDK (`f6ded0be...`). ROCm's bundled LLVM 23 is a different revision and is not a drop-in replacement. Downloads are cached in BuildKit; this SDK stays in the build stage, not the runtime image. Build output is unbuffered.

## Deploy

```bash
kubectl apply -f freetoken/k8s.yaml
kubectl -n apps-ml rollout status deployment/freetoken-gfx906 --timeout=1800s
kubectl -n apps-ml port-forward service/freetoken-gfx906 1919:1919
```

The endpoint is cluster-internal: `http://freetoken-gfx906.apps-ml.svc.cluster.local:1919/v1`. No public ingress or authentication is configured. Do not expose it publicly without access controls.

This test cluster has no AMD device-plugin allocation, so the pod uses privileged device access, like the existing ROCm workloads. All four GPUs participate in tensor parallelism (`--tp-size 4`); there is no exclusive GPU reservation. KV cache is capped at 4096 tokens, context at 2048, and HIP graphs are enabled for batch sizes 1, 2 and 4. `--disable-pynccl` selects PyTorch's RCCL path rather than upstream's CUDA-only custom communicator. Set `--cuda-graph-max-bs 0` to diagnose failures without graphs.

Readiness checks the JSON status, not just HTTP 200: upstream `/health` also returns HTTP 200 while loading or reporting a backend error.

## Checks

```bash
python3 freetoken/smoke-test.py --url http://127.0.0.1:1919 --benchmark
kubectl apply -f freetoken/probe.yaml
kubectl -n apps-ml wait --for=condition=Ready pod/freetoken-probe --timeout=300s
kubectl -n apps-ml cp freetoken/gpu-check.py freetoken-probe:/tmp/gpu-check.py
kubectl -n apps-ml exec freetoken-probe -- python3 /tmp/gpu-check.py
kubectl -n apps-ml exec freetoken-probe -- env OMP_NUM_THREADS=2 HSA_FORCE_FINE_GRAIN_PCIE=1 torchrun --standalone --nproc-per-node=4 /tmp/gpu-check.py
```

`probe.yaml` creates a disposable diagnostic pod using the built FreeToken image. It is not needed by the server. The diagnostic pod was removed after validation.

## Results (2026-10-17)

- Node: `kube-worker6.arkprojects.lan`, four 32 GiB MI50s, `gfx906:sramecc+:xnack-`.
- Deployment: `apps-ml/freetoken-gfx906`, ready, TP=4, FP16, Triton attention, RCCL, HIP graphs.
- FP16 matrix multiplication against a CPU reference passed on all four GPUs. Four-rank RCCL all-reduce returned `10` on every rank.
- TP=1 and TP=4 without graphs passed the API smoke test. The final TP=4 deployment with graphs passed the same test, also through the Kubernetes Service.
- `/health`, `/v1/models`, non-streaming chat, SSE chat with usage accounting, and four concurrent chat requests passed. Answers included `2 + 2 = 4.` and `Paris`, matching Transformers eager FP16 on the same checkpoint.
- Kernel checks: **60 passed** (41 attention tests and 19 activation/norm/sampling/ROCm launch tests; explicit bfloat16 parameterizations were excluded from the latter group).
- Two 128-output-token streaming requests: **82.17 / 82.28 decode tokens/s**. End-to-end rates were 80.36 / 55.45 tokens/s, TTFT 47 / 765 ms. The second request reused a cached prefix; these timings can include JIT warmup and are short smoke measurements, not a production benchmark or a TP=1 speed comparison.

Only this small dense FP16 model was validated end-to-end. Large MoE models, expert offload, BF16 models and quantized model execution have not been qualified by this test.

Raw build logs, server logs and smoke-test JSON are saved locally in `freetoken/logs/` (git-ignored).

Kernel test commands (inside the diagnostic pod, after `uv pip install pytest`):

```bash
python3 -m pytest /opt/FreeToken/tests/kernels/test_triton_attention.py -q
python3 -m pytest /opt/FreeToken/tests/kernels/test_triton_fallbacks.py /opt/FreeToken/tests/kernels/test_rocm_launch_kwargs.py -k 'not bfloat16' -q
```

## Remove test resources

```bash
kubectl delete -f freetoken/k8s.yaml
kubectl -n apps-ml delete pod freetoken-probe --ignore-not-found
```

The shared model cache is left intact.
