#!/usr/bin/env bash
set -euo pipefail

# Run inside the approved test pod, with no other GPU workload active.
: "${BENCH_DIR:=/data/bench}"
: "${BENCH_CASES:=/data/screening.jsonl}"
: "${BENCH_REFERENCE:=/data/runs/validate-base-a/results.jsonl}"
: "${BENCH_RUN:=runtime-screen-01}"
out="/data/runs/$BENCH_RUN"
test ! -e "$out"
mkdir "$out"
python "$BENCH_DIR/variants.py" --out "$out/configs"

for name in eg4096 cpu56 node0-cpu38 copy64-single-part; do
  python "$BENCH_DIR/native_bench.py" \
    --config "$out/configs/$name.json" --cases "$BENCH_CASES" \
    --out "$out/$name" --dump
  if python "$BENCH_DIR/compare.py" "$BENCH_REFERENCE" \
    "$out/$name/results.jsonl" --require-logits > "$out/$name/verdict.json"; then
    echo "NUMERICAL PASS: $name (timing validation runs is not a speedup claim)"
  else
    echo "NUMERICAL REJECT: $name"
    cat "$out/$name/verdict.json"
  fi
done
