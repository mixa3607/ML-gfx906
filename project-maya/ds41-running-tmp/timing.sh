#!/usr/bin/env bash
set -euo pipefail

# Run after numerical validation, with exclusive use of the four GPUs.
: "${BENCH_DIR:=/data/bench}"
: "${BENCH_GATE:=/data/runs/combined-screen-01}"
: "${BENCH_RUN:=fair-time-01}"
: "${BENCH_SEED:=20261024}"
: "${BENCH_CANDIDATES:=copy1-cpu56 copy1-cpu56-eg4096 copy1-cpu56-eg4096-chunk4096}"
out="/data/runs/$BENCH_RUN"
test ! -e "$out"
mkdir "$out"

# Refuse missing verdicts, changed configs, or a completely rejected shortlist.
python - "$BENCH_GATE" "$out/candidates.txt" "$BENCH_CANDIDATES" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

gate, target = map(Path, sys.argv[1:3])
accepted = []
eligibility = []
for name in sys.argv[3].split():
    invalidation = gate / name / 'invalidation.json'
    if invalidation.exists():
        raise SystemExit(f'Candidate invalidated by a later check: {name}: {invalidation}')
    verdict = json.loads((gate / name / 'verdict.json').read_text())
    if verdict['bit_exact_on_tested_rows'] is not True:
        continue
    config = gate / 'configs' / f'{name}.json'
    manifest = json.loads((gate / name / 'manifest.json').read_text())
    if hashlib.sha256(config.read_bytes()).hexdigest() != manifest['config_sha256']:
        raise SystemExit(f'Config changed after validation: {name}')
    accepted.append(name)
    rows = [json.loads(line) for line in (gate / name / 'results.jsonl').read_text().splitlines()]
    eligibility.append({'name': name, 'gate': str(gate / name),
                        'tested_pp': sorted({r['pp'] for r in rows}),
                        'tested_logit_rows': sum(len(r['logits']['rows']) for r in rows)})
if not accepted:
    raise SystemExit('No numerically accepted timing candidates')
target.write_text('\n'.join(accepted) + '\n')
target.with_name('eligibility.json').write_text(json.dumps(eligibility, indent=2) + '\n')
PY

python "$BENCH_DIR/corpus.py" build --source /data/wiki-final.jsonl \
  --out "$out/warmup.jsonl" --split warmup --count 12 --pp 2048 --seed "$BENCH_SEED"
python "$BENCH_DIR/corpus.py" build --source /data/wiki-final.jsonl \
  --out "$out/dev.jsonl" --split dev --count 6 --pp 2048 4096 8192 --seed "$BENCH_SEED"
cat "$out/warmup.jsonl" "$out/dev.jsonl" > "$out/cases.jsonl"

python "$BENCH_DIR/native_bench.py" --config "$BENCH_DIR/baseline.json" \
  --cases "$out/cases.jsonl" --out "$out/control-a"
while IFS= read -r name; do
  python "$BENCH_DIR/native_bench.py" --config "$BENCH_GATE/configs/$name.json" \
    --cases "$out/cases.jsonl" --out "$out/$name"
done < "$out/candidates.txt"
python "$BENCH_DIR/native_bench.py" --config "$BENCH_DIR/baseline.json" \
  --cases "$out/cases.jsonl" --out "$out/control-b"

# Token checks are additional consistency checks, not a full-logit parity proof.
for name in control-b $(cat "$out/candidates.txt"); do
  if python "$BENCH_DIR/compare.py" "$out/control-a/results.jsonl" \
    "$out/$name/results.jsonl" > "$out/$name/timing-comparison.json"; then
    echo "TIMING TOKEN CONSISTENCY PASS: $name"
  else
    echo "TIMING TOKEN CONSISTENCY FAIL: $name"
    cat "$out/$name/timing-comparison.json"
  fi
done
