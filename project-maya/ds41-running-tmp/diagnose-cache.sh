#!/usr/bin/env bash
set -euo pipefail

# Diagnostic only: frozen expert placement is a different reference policy.
: "${BENCH_DIR:=/data/bench}"
: "${BENCH_RUN:=cache-diagnosis-01}"
out="/data/runs/$BENCH_RUN"
test ! -e "$out"
mkdir "$out"
python - "$BENCH_DIR" "$out" <<'PY'
import copy
import json
from pathlib import Path
import sys

bench, out = map(Path, sys.argv[1:])
base = json.loads((bench / 'baseline.json').read_text())
rows = [json.loads(s) for s in Path('/data/runs/fair-copy48-time-01/cases.jsonl').read_text().splitlines()]
(out / 'cases.jsonl').write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in (rows[0], rows[-1])) + '\n')
(out / 'single.jsonl').write_text(json.dumps(rows[0], ensure_ascii=False) + '\n')
configs = {}
cfg = copy.deepcopy(base)
cfg['args'].append('--no-expert-cache')
configs['frozen-mmap48'] = cfg
for threads in (48, 56):
    cfg = copy.deepcopy(base)
    cfg['args'][cfg['args'].index('--mmap-experts') + 1] = 'off'
    cfg['args'][cfg['args'].index('--cpu-threads') + 1] = str(threads)
    cfg['args'].append('--no-expert-cache')
    cfg['env']['DS4_COPY_NUMA'] = '1'
    cfg['require_full_copies'] = True
    configs[f'frozen-copy{threads}'] = cfg
cfg = json.loads(Path('/data/runs/full-copy-screen-01/configs/copy-all-numa1.json').read_text())
cfg['env']['DS4_CHECK_SWAPS'] = '1'
configs['adaptive-copy48-check-swaps'] = cfg
for name, cfg in configs.items():
    cfg['name'] = name
    (out / f'{name}.json').write_text(json.dumps(cfg, indent=2) + '\n')
PY

for name in frozen-mmap48 frozen-copy48 frozen-copy56; do
  python "$BENCH_DIR/native_bench.py" --config "$out/$name.json" \
    --cases "$out/cases.jsonl" --out "$out/$name" --dump
done
failed=0
for name in frozen-copy48 frozen-copy56; do
  if python "$BENCH_DIR/compare.py" "$out/frozen-mmap48/results.jsonl" \
    "$out/$name/results.jsonl" --require-logits > "$out/$name/verdict.json"; then
    echo "FROZEN-SOURCE PARITY PASS: $name (not acceptance under adaptive policy)"
  else
    failed=1
    echo "FROZEN-SOURCE PARITY FAIL: $name"
    cat "$out/$name/verdict.json"
  fi
done
name=adaptive-copy48-check-swaps
python "$BENCH_DIR/native_bench.py" --config "$out/$name.json" \
  --cases "$out/single.jsonl" --out "$out/$name" --dump
if grep -q 'ds4 cache:.*MISMATCH' "$out/$name/engine.log"; then
  echo 'SWAP BYTE CHECK FAILED' >&2
  exit 1
fi
grep -q 'ds4 cache:.*matches the model file' "$out/$name/engine.log"
echo 'SWAP BYTE CHECK PASSED: checks exercised; see engine.log'
exit "$failed"
