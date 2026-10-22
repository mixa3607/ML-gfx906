"""Isolate flow's TP member reads: file source vs one/two NUMA RAM parts."""
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys

import numpy as np

bench = runpy.run_path(str(Path(__file__).with_name('ds41-tune.py')))
OUT, ROOT, MODEL, save, Engine = (bench[k] for k in ('OUT', 'ROOT', 'MODEL', 'save', 'Engine'))
OUT.mkdir(parents=True, exist_ok=True)
pack = OUT / 'pack'
with (OUT / 'pack.log').open('w') as log:
    subprocess.run([sys.executable, 'tools/ds4/pack_gguf.py', '--model', str(MODEL), '--out', str(pack)],
                   cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
tok, corpus, _ = bench['make_cases'](pack)
bio = next(c for c in corpus if c['name'] == 'biology-2048')
cases = [{**bio, 'name': 'biology-512', 'ids': bio['ids'][:384] + bio['ids'][-128:]}]
cases += [c for c in corpus if c['name'] in ('climate-2048', 'history-8192')]
# TG1 dumps only the prompt-last row: no CPU decode reduction differences between NH1/NH2.
cases = [{**c, 'tg': 1} for c in cases]
env = {'DS4_HIP_ATTN_SWIZZLE': '1', 'DS4_RING_MB': '400', 'DS4_FLOW_TP': '1',
       'DS4_SKIP_UNPICKED': '0', 'DS4_FLOW_STATS': '1', 'DS4_PREFILL_STATS': '1',
       'DS4_CHUNK_MIN': '256', 'DS4_PATH_PICK': '0', 'DS4_RECENT': '0'}
report = {'completed': False, 'all_exact': False, 'runs': {}}
save(OUT / 'flow-copy-parity.json', report)
for label, mmap, nh in [('files', 'on', '1'), ('ram-nh1', 'off', '1'), ('ram-nh2', 'off', '2')]:
    directory = OUT / label
    config = {'cpu': 56, 'chunk': 4096, 'reserve': 896, 'tp': 2, 'mmap': mmap,
              'extra_args': ['--no-expert-cache'],
              'env': {**env, 'DS4_COPY_NUMA': nh, 'DS4_SERVE_DUMP': str(directory / 'logits')}}
    save(OUT / (label + '-config.json'), config)
    engine = Engine(directory, config, pack)
    try:
        results = [engine.request(c, tok) for c in cases]
        assert all(r['cached_tokens'] == 0 for r in results)
    finally:
        engine.close()
    log = (directory / 'engine.log').read_text()
    assert 'ds4 prompt stream' in log
    if mmap == 'off':
        assert f'{nh} NUMA parts' in log
        assert re.search(r'[1-9][0-9]* from RAM', log)
    else:
        assert re.search(r'[1-9][0-9]* from the files', log)
    placement = re.findall(r'CUDA\d.*?\(\d+ of \d+ in VRAM\)', log)
    assert len(placement) == 4
    dumps = []
    for i, case in enumerate(cases, 1):
        raw = (directory / f'logits.{i}.f32').read_bytes()
        assert len(raw) == len(tok.tokens) * 4
        assert np.isfinite(np.frombuffer(raw, dtype=np.float32)).all()
        dumps.append({'case': case['name'], 'sha256': hashlib.sha256(raw).hexdigest()})
    report['runs'][label] = {'placement': placement, 'requests': results, 'dumps': dumps}
    save(OUT / 'flow-copy-parity.json', report)
reference = report['runs']['files']
assert all(r['placement'] == reference['placement'] for r in report['runs'].values()), 'Expert placement differs'
report['all_exact'] = all(r['dumps'] == reference['dumps'] for r in report['runs'].values())
report['completed'] = True
save(OUT / 'flow-copy-parity.json', report)
print('FLOW COPY RESULT', json.dumps(report, ensure_ascii=False), flush=True)
assert report['all_exact'], 'Source-only exactness failed: do not accept the RAM-copy path'
