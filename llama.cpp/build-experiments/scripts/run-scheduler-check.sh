#!/usr/bin/env bash
# Run inside a llama.cpp ROCm container. Results are written under --results.
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "usage: $0 <source-dir> <results-dir> <stock|maxocc|maxilp|iterativeilp|maxilp-unroll100>" >&2
    exit 2
fi

source_dir=$1
results_dir=$2
variant=$3

case "$variant" in
    stock)
        hip_flags=()
        ;;
    maxocc)
        hip_flags=(-mllvm -amdgpu-sched-strategy=iterative-maxocc)
        ;;
    maxilp)
        hip_flags=(-mllvm -amdgpu-sched-strategy=max-ilp)
        ;;
    iterativeilp)
        hip_flags=(-mllvm -amdgpu-sched-strategy=iterative-ilp)
        ;;
    maxilp-unroll100)
        hip_flags=(-mllvm -amdgpu-sched-strategy=max-ilp -mllvm -unroll-threshold=100)
        ;;
    *)
        echo "unknown variant: $variant" >&2
        exit 2
        ;;
esac

build_dir="$source_dir/build-experiment-$variant"
mkdir -p "$results_dir"

git -C "$source_dir" rev-parse HEAD > "$results_dir/llama-commit.txt"
hipcc --version > "$results_dir/hipcc-version.txt"
rocminfo > "$results_dir/rocminfo.txt"
env | sort > "$results_dir/environment.txt"
printf '%q ' "${hip_flags[@]}" > "$results_dir/hip-flags.txt"
printf '\n' >> "$results_dir/hip-flags.txt"

export HIPCXX="$(hipconfig -l)/clang"
export HIP_PATH="$(hipconfig -R)"

cmake -S "$source_dir" -B "$build_dir" \
    -DGGML_HIP=ON \
    -DGGML_HIP_GRAPHS=ON \
    -DGGML_HIP_RCCL=ON \
    -DAMDGPU_TARGETS=gfx906 \
    -DGGML_BACKEND_DL=ON \
    -DGGML_RPC=ON \
    -DGGML_CPU_ALL_VARIANTS=ON \
    -DGGML_AVX512=ON \
    -DGGML_AVX512_VBMI=ON \
    -DGGML_AVX512_VNNI=ON \
    -DGGML_AVX512_BF16=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_HIP_FLAGS="${hip_flags[*]}" \
    -DLLAMA_BUILD_TESTS=OFF \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    2>&1 | tee "$results_dir/cmake-configure.log"
cmake --build "$build_dir" --config Release -j"$(nproc)" \
    2>&1 | tee "$results_dir/cmake-build.log"

cp "$build_dir/CMakeCache.txt" "$results_dir/"
cp "$build_dir/compile_commands.json" "$results_dir/"
sha256sum "$build_dir/bin/libggml-hip.so" > "$results_dir/libggml-hip.sha256"
ldd "$build_dir/bin/libggml-hip.so" > "$results_dir/libggml-hip.ldd.txt"

bench="$build_dir/bin/llama-bench"
run_bench() {
    local name=$1
    local repo=$2
    "$bench" --hf-repo "$repo" --flash-attn on \
        --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
        --n-gen 256 --n-depth 0 --split-mode layer --device ROCm0 \
        --output jsonl | tee "$results_dir/$name.jsonl"
}

run_bench qwen 'unsloth/Qwen3.5-9B-GGUF:Q8_0'
run_bench gemma 'bartowski/google_gemma-4-26B-A4B-it-GGUF:Q4_K_L'

rocprofv3 --kernel-trace --stats --summary --summary-output-file stdout -- \
    "$bench" --hf-repo 'unsloth/Qwen3.5-9B-GGUF:Q8_0' --flash-attn on \
    --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
    --n-gen 0 --n-depth 0 --split-mode layer --device ROCm0 --output jsonl \
    > "$results_dir/qwen-pp-rocprof.log" 2>&1

rocprofv3 --kernel-trace --stats --summary --summary-output-file stdout -- \
    "$bench" --hf-repo 'bartowski/google_gemma-4-26B-A4B-it-GGUF:Q4_K_L' --flash-attn on \
    --n-prompt 2048 --ubatch-size 2048 --batch-size 2048 \
    --n-gen 0 --n-depth 0 --split-mode layer --device ROCm0 --output jsonl \
    > "$results_dir/gemma-pp-rocprof.log" 2>&1
