"""Bounded full-model logit checks, separate from throughput measurements."""
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

import numpy as np

bench = runpy.run_path(str(Path(__file__).with_name('ds41-tune.py')))
OUT, ROOT, MODEL = (bench[k] for k in ('OUT', 'ROOT', 'MODEL'))
save, Engine = (bench[k] for k in ('save', 'Engine'))
experiment = os.environ['MAYA_EXPERIMENT_EXPECTED']
OUT.mkdir(parents=True, exist_ok=True)
pack = OUT / 'pack'
with (OUT / 'pack.log').open('w') as log:
    subprocess.run([sys.executable, 'tools/ds4/pack_gguf.py', '--model', str(MODEL),
                    '--out', str(pack)], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
tok, corpus, checks = bench['make_cases'](pack)
cases = [{**case, 'tg': 64} for case in corpus if case['name'] in ('climate-2048', 'history-8192')]
biology = next(case for case in corpus if case['name'] == 'biology-2048')
short = {**biology, 'name': 'biology-512', 'tg': 64, 'ids': biology['ids'][:384] + biology['ids'][-128:]}
cases.insert(0, short)
save(OUT / 'inputs/biology-2048/short-ids.json', short['ids'])
base_env = {'DS4_HIP_ATTN_SWIZZLE': '1', 'DS4_RING_MB': '400', 'DS4_FLOW_TP': '0',
            'DS4_SKIP_UNPICKED': '0', 'DS4_FLOW_STATS': '1', 'DS4_PREFILL_STATS': '1',
            'DS4_CHUNK_MIN': '256', 'DS4_PATH_PICK': '0', 'DS4_RECENT': '0'}
common = {'cpu': 56, 'chunk': 4096, 'reserve': 896, 'tp': 2, 'mmap': 'off',
          'extra_args': ['--no-expert-cache']}
baseline = '/baseline/maya-ds4'
variants = [('original-a', baseline, {}, 4096), ('original-b', baseline, {}, 4096),
            ('patched-off', str(ROOT / 'build-hip/maya-ds4'), {}, 4096)]
if experiment == 'pr297':
    variants.append(('patched-on', str(ROOT / 'build-hip/maya-ds4'), {'DS4_SKIP_UNPICKED': '1'}, 4096))
elif experiment == 'pr377':
    variants += [('original-chunk2048', baseline, {}, 2048),
                 ('patched-on', str(ROOT / 'build-hip/maya-ds4'), {'DS4_FLOW_TP': '1'}, 4096)]
elif experiment == 'pr377-360':
    # Its baseline is the verified PR377 image; isolate the pump in the flow path.
    base_env['DS4_FLOW_TP'] = '1'
    base_env['DS4_FLOW_PUMP_WAIT'] = '0'
    variants.append(('patched-on', str(ROOT / 'build-hip/maya-ds4'), {'DS4_FLOW_PUMP_WAIT': '1'}, 4096))
else:
    raise SystemExit('Unknown experiment')

report = {'experiment': experiment, 'completed': False, 'runs': {}, 'comparisons': {}}
save(OUT / 'parity.json', report)
for label, binary, extra, chunk in variants:
    directory = OUT / label
    config = {**common, 'binary': binary, 'chunk': chunk,
              'env': {**base_env, **extra, 'DS4_SERVE_DUMP': str(directory / 'logits')}}
    save(OUT / (label + '-config.json'), config)
    engine = Engine(directory, config, pack)
    try:
        results = [engine.request(case, tok) for case in cases]
        assert all(r['cached_tokens'] == 0 for r in results)
        check_results = [engine.request(case, tok) for case in checks]
        assert all(r['check_pass'] for r in check_results)
    finally:
        engine.close()
    dumps = []
    for n, case in enumerate(cases, 1):
        path = directory / f'logits.{n}.f32'
        raw = path.read_bytes()
        # One prompt-last row and 63 decode rows, all vocabulary entries.
        assert len(raw) == 64 * len(tok.tokens) * 4
        values = np.frombuffer(raw, dtype=np.float32).reshape(64, -1)
        assert values.shape[1] > 100000 and np.isfinite(values).all()
        dumps.append({'case': case['name'], 'bytes': len(raw), 'rows': len(values),
                      'vocab': values.shape[1], 'sha256': hashlib.sha256(raw).hexdigest()})
    report['runs'][label] = {'requests': results, 'checks': check_results, 'dumps': dumps,
                             'binary_sha256': hashlib.sha256(Path(binary).read_bytes()).hexdigest()}
    save(OUT / 'parity.json', report)


def compare(left, right):
    rows = []
    for n, case in enumerate(cases, 1):
        a_raw = (OUT / left / f'logits.{n}.f32').read_bytes()
        b_raw = (OUT / right / f'logits.{n}.f32').read_bytes()
        a = np.frombuffer(a_raw, dtype=np.float32).reshape(64, -1)
        b = np.frombuffer(b_raw, dtype=np.float32).reshape(64, -1)
        assert a.shape == b.shape
        ai = json.loads((OUT / left / case['name'] / 'output-ids.json').read_text())
        bi = json.loads((OUT / right / case['name'] / 'output-ids.json').read_text())
        prefix = next((i for i, (x, y) in enumerate(zip(ai, bi)) if x != y), len(ai))
        # Beyond the first differing generated token the input histories differ.
        comparable = min(64, prefix + 1)
        x, y = a[:comparable].astype(np.float64), b[:comparable].astype(np.float64)
        x -= x.max(axis=1, keepdims=True)
        y -= y.max(axis=1, keepdims=True)
        lx = x - np.log(np.exp(x).sum(axis=1, keepdims=True))
        ly = y - np.log(np.exp(y).sum(axis=1, keepdims=True))
        kl = (np.exp(lx) * (lx - ly)).sum(axis=1)
        rows.append({'case': case['name'], 'bit_identical': a_raw == b_raw,
                     'prompt_last_bit_identical': a[0].tobytes() == b[0].tobytes(),
                     'identical_greedy_prefix': prefix, 'comparable_rows': comparable,
                     'max_abs_comparable': float(np.abs(a[:comparable] - b[:comparable]).max()),
                     'prompt_last_kl': float(kl[0]), 'max_kl_comparable': float(kl.max()),
                     'argmax_agreement_comparable': float((a[:comparable].argmax(1) == b[:comparable].argmax(1)).mean())})
    return rows


for left, right in [('original-a', 'original-b'), ('original-a', 'patched-off'),
                    ('original-a', 'patched-on')]:
    report['comparisons'][left + '-vs-' + right] = compare(left, right)
if 'original-chunk2048' in report['runs']:
    report['comparisons']['chunk-floor'] = compare('original-a', 'original-chunk2048')
report['completed'] = True
report['all_exact'] = all(r['bit_identical'] for rows in report['comparisons'].values() for r in rows)
save(OUT / 'parity.json', report)
print('NUMERICAL RESULT', json.dumps(report, ensure_ascii=False), flush=True)
if experiment in ('pr297', 'pr377-360') and not report['all_exact']:
    raise SystemExit('Exactness check failed; do not proceed to throughput tests automatically')
if experiment == 'pr297':
    log = (OUT / 'patched-on/engine.log').read_text()
    skipped = [int(n) for n in re.findall(r'(\d+) unpicked experts skipped', log)]
    assert skipped and max(skipped) > 0, 'Pruning path was not exercised'
elif experiment in ('pr377', 'pr377-360'):
    log = (OUT / 'patched-on/engine.log').read_text()
    assert 'ds4 prompt stream' in log, 'Flow path was not exercised'
