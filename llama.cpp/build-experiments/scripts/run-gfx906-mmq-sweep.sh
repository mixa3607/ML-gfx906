#!/usr/bin/env bash
# Run inside the ROCm 7.14 container after installing the gfx906 MMQ config under test.
set -euo pipefail

if [ "$#" -ne 3 ]; then
    echo "usage: $0 <source-dir> <results-dir> <variant-name>" >&2
    exit 2
fi

source_dir=$1
results_dir=$2
variant=$3
build_dir="$source_dir/build-experiment-$variant"

mkdir -p "$results_dir"
git -C "$source_dir" rev-parse HEAD > "$results_dir/llama-commit.txt"
git -C "$source_dir" diff -- ggml/src/ggml-cuda/mmq.cuh ggml/src/ggml-cuda/mmq-config-gfx906.cuh \
    > "$results_dir/source.patch"
cp "$source_dir/ggml/src/ggml-cuda/mmq-config-gfx906.cuh" "$results_dir/"
hipcc --version > "$results_dir/hipcc-version.txt"
rocminfo > "$results_dir/rocminfo.txt"
env | sort > "$results_dir/environment.txt"

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
    -DCMAKE_HIP_FLAGS='-mllvm -amdgpu-sched-strategy=max-ilp' \
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

llvm_bin="$(hipconfig -l)"
: > "$results_dir/hsaco-resources.txt"
for pair in q8_0:8 q4_k:12 q5_k:13 q6_k:14; do
    file=${pair%:*}
    type=${pair#*:}
    object="$build_dir/ggml/src/ggml-hip/CMakeFiles/ggml-hip.dir/__/ggml-cuda/template-instances/mmq-instance-$file.cu.o"
    fatbin="$results_dir/$file.fatbin"
    hsaco="$results_dir/$file.hsaco"
    "$llvm_bin/llvm-objcopy" --dump-section .hip_fatbin="$fatbin" "$object"
    "$llvm_bin/clang-offload-bundler" --unbundle --type=o \
        --targets=hipv4-amdgcn-amd-amdhsa--gfx906 --input="$fatbin" --output="$hsaco"
    printf '\n=== type %s, J=64, fallback=false ===\n' "$type" >> "$results_dir/hsaco-resources.txt"
    "$llvm_bin/llvm-readobj" --notes "$hsaco" \
        | grep -A12 "type${type}ELi64ELb0" \
        | grep -E 'name:|private_segment_fixed_size|sgpr_count|vgpr_count|wavefront_size' \
        | sed -n '1,6p' >> "$results_dir/hsaco-resources.txt"
done
