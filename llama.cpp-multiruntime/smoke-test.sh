#!/usr/bin/env bash
set -euo pipefail
export LLAMA_ARG_LOG_VERBOSITY=4

log_dir="$(mktemp -d /tmp/llama-smoke.XXXXXX)"
rpc_pid=""
cleanup() {
    if [[ -n "$rpc_pid" ]]; then
        kill "$rpc_pid" 2>/dev/null || true
        wait "$rpc_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT
echo "Smoke logs: $log_dir"

for backend in /app/libggml-{cuda,hip,rpc}.so; do
    dependencies="$(ldd "$backend")"
    if grep -q 'not found' <<< "$dependencies"; then
        printf '%s\n%s\n' "$backend" "$dependencies" >&2
        exit 1
    fi
done

timeout 60 llama-cli --list-devices 2>&1 | tee "$log_dir/devices.log"
grep -q 'loaded CPU backend' "$log_dir/devices.log"
grep -q 'loaded RPC backend' "$log_dir/devices.log"
cuda_count="$(grep -cE '^  CUDA[0-9]+:' "$log_dir/devices.log" || true)"
rocm_count="$(grep -cE '^  ROCm[0-9]+:' "$log_dir/devices.log" || true)"
[[ "$cuda_count" == "${SMOKE_CUDA_DEVICES:-2}" ]]
[[ "$rocm_count" == "${SMOKE_ROCM_DEVICES:-4}" ]]

ggml-rpc-server --host 127.0.0.1 --port 50052 --device CPU --threads 2 > "$log_dir/rpc-server.log" 2>&1 &
rpc_pid=$!
rpc_ready=0
for ((i = 0; i < 30; i++)); do
    kill -0 "$rpc_pid" || { cat "$log_dir/rpc-server.log"; exit 1; }
    if timeout 10 llama-cli --rpc 127.0.0.1:50052 --list-devices > "$log_dir/rpc-client.log" 2>&1 && \
        grep -qE '^  RPC.*127\.0\.0\.1:50052' "$log_dir/rpc-client.log"; then
        rpc_ready=1
        break
    fi
    sleep 1
done
cat "$log_dir/rpc-client.log"
[[ "$rpc_ready" == 1 ]]

# Optional tiny-model smoke: eight tokens, bounded context, no benchmark.
if [[ -n "${SMOKE_MODEL:-}" ]]; then
    common=(-m "$SMOKE_MODEL" -p 'Once upon a time' -n 8 -c 256 -b 32 -ub 32 -t 2 --seed 1 --temp 0 --no-warmup)
    run_model() {
        local name="$1"
        shift
        timeout 120 llama-completion "${common[@]}" "$@" 2>&1 | tee "$log_dir/$name.log"
    }
    run_model cpu --device none -ngl 0
    for ((i = 0; i < cuda_count; i++)); do
        run_model "cuda$i" --device "CUDA$i" -ngl 99
        grep -Eq "CUDA$i .*model buffer size" "$log_dir/cuda$i.log"
    done
    for ((i = 0; i < rocm_count; i++)); do
        run_model "rocm$i" --device "ROCm$i" -ngl 99
        grep -Eq "ROCm$i .*model buffer size" "$log_dir/rocm$i.log"
    done
    run_model mixed --device CUDA0,ROCm0 --split-mode layer --tensor-split 1,1 -ngl 99
    grep -Eq 'CUDA0 .*model buffer size' "$log_dir/mixed.log"
    grep -Eq 'ROCm0 .*model buffer size' "$log_dir/mixed.log"
    run_model rpc --rpc 127.0.0.1:50052 --device RPC0 -ngl 99
    grep -Eq 'RPC0.*model buffer size' "$log_dir/rpc.log"
fi

echo "PASS: CPU, RPC, $cuda_count CUDA devices, $rocm_count ROCm devices"
