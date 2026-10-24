#!/usr/bin/env bash
set -euo pipefail

# Run inside the approved pod. This batch extends parity to multi-chunk prompts.
: "${BENCH_DIR:=/data/bench}"
: "${BENCH_RUN:=combined-screen-01}"
out="/data/runs/$BENCH_RUN"
test ! -e "$out"
mkdir "$out"
python "$BENCH_DIR/variants.py" --combined-only --out "$out/configs"
python "$BENCH_DIR/corpus.py" build --source /data/wiki-final.jsonl \
  --out "$out/medium.jsonl" --split dev --count 2 --pp 4096 8192 --seed 20261025
cat /data/screening.jsonl "$out/medium.jsonl" > "$out/cases.jsonl"

python "$BENCH_DIR/native_bench.py" --config "$BENCH_DIR/baseline.json" \
  --cases "$out/cases.jsonl" --out "$out/reference" --dump
for name in copy1-cpu56 copy1-cpu56-eg4096 copy1-cpu56-eg4096-chunk4096; do
  python "$BENCH_DIR/native_bench.py" \
    --config "$out/configs/$name.json" --cases "$out/cases.jsonl" \
    --out "$out/$name" --dump
  if python "$BENCH_DIR/compare.py" "$out/reference/results.jsonl" \
    "$out/$name/results.jsonl" --require-logits > "$out/$name/verdict.json"; then
    echo "EXTENDED NUMERICAL PASS: $name"
  else
    echo "EXTENDED NUMERICAL REJECT: $name"
    cat "$out/$name/verdict.json"
  fi
done
