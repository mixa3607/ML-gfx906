#!/usr/bin/env python3
"""Generate runtime candidates; these are not validated recommendations."""
import argparse
import copy
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--full-copy-only', action='store_true',
                      help='Follow-up: all CPU experts, one or two NUMA parts')
    mode.add_argument('--combined-only', action='store_true',
                      help='Full single-part copies plus CPU56, Engram cache and chunk candidates')
    a = p.parse_args()
    baseline = json.loads(Path(__file__).with_name('baseline.json').read_text())
    a.out.mkdir(parents=True, exist_ok=True)
    variants = {}
    cfg = copy.deepcopy(baseline)
    cfg['env']['DS4_ENGRAM_CACHE_MB'] = '4096'
    variants['eg4096'] = cfg
    cfg = copy.deepcopy(baseline)
    cfg['args'][cfg['args'].index('--cpu-threads') + 1] = '56'
    variants['cpu56'] = cfg
    cfg = copy.deepcopy(baseline)
    cfg['args'][cfg['args'].index('--cpu-threads') + 1] = '38'
    cfg['cpu_affinity'] = list(range(38))
    variants['node0-cpu38'] = cfg
    cfg = copy.deepcopy(baseline)
    cfg['env']['DS4_COPY_GB'] = '64'
    cfg['env']['DS4_COPY_NUMA'] = '1'
    variants['copy64-single-part'] = cfg
    if a.full_copy_only:
        variants = {}
        for parts in (1, 2):
            cfg = copy.deepcopy(baseline)
            cfg['args'][cfg['args'].index('--mmap-experts') + 1] = 'off'
            cfg['env']['DS4_COPY_NUMA'] = str(parts)
            cfg['require_full_copies'] = True
            variants[f'copy-all-numa{parts}'] = cfg
    if a.combined_only:
        variants = {}
        for name, cache, chunk in [('copy1-cpu56', '256', '2048'),
                                   ('copy1-cpu56-eg4096', '4096', '2048'),
                                   ('copy1-cpu56-eg4096-chunk4096', '4096', '4096')]:
            cfg = copy.deepcopy(baseline)
            for key, value in [('--mmap-experts', 'off'), ('--cpu-threads', '56'),
                               ('--prefill-chunk', chunk)]:
                cfg['args'][cfg['args'].index(key) + 1] = value
            cfg['env']['DS4_COPY_NUMA'] = '1'
            cfg['env']['DS4_ENGRAM_CACHE_MB'] = cache
            cfg['require_full_copies'] = True
            variants[name] = cfg
    for name, cfg in variants.items():
        cfg['name'] = name
        with (a.out / f'{name}.json').open('x') as f:
            f.write(json.dumps(cfg, indent=2) + '\n')


if __name__ == '__main__':
    main()
