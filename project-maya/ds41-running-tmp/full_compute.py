#!/usr/bin/env python3
"""Allowlisted full-compute policy and serial warm runtime comparison."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys


POLICY = 'full-compute-v1'
ROOT = Path(__file__).resolve().parent
ENV_VALUES = {
    'DS4_COPY_NUMA': {'1', '2'},
    'DS4_ENGRAM_CACHE_MB': {'256', '4096'},
    'STRATA_DS4_PROMPT_SKIP': {'0', '1'},
    'DS4_TP_GGUF_UNEVEN': {'1'},
    'DS4_FLOW_TP': {'1'},
    'DS4_FLOW_PUMP_WAIT': {'0', '1'},
    'DS4_TP_CHECK': {'1'},
}
ARG_VALUES = {
    '--cpu-threads': {'48', '56'},
    '--prefill-chunk': {'2048', '4096'},
    '--mmap-experts': {'auto', 'off'},
}


def baseline():
    return json.loads((ROOT / 'baseline.json').read_text())


def validate_config(cfg):
    """Timing eligibility, not a proof of quality, parity, or context retention."""
    base = baseline()
    if cfg.get('policy') != POLICY:
        raise ValueError('Explicit full-compute-v1 policy required')
    allowed_keys = set(base) | {'policy', 'require_full_copies'}
    if set(cfg) - allowed_keys:
        raise ValueError('Unknown configuration keys')
    for key in ('exe', 'cwd', 'seed_profile'):
        if cfg[key] != base[key]:
            raise ValueError(f'Fixed model/runtime path changed: {key}')
    args = cfg['args']
    if args[-1:] == ['--verbose']:
        args = args[:-1]
    if len(args) != len(base['args']) or args[::2] != base['args'][::2]:
        raise ValueError('Unknown, duplicate, missing, or reordered engine options')
    for key, value, fixed in zip(args[::2], args[1::2], base['args'][1::2]):
        if value not in ARG_VALUES.get(key, {fixed}):
            raise ValueError(f'Unapproved engine option: {key}={value}')
    env = cfg['env']
    if set(env) - (set(base['env']) | set(ENV_VALUES)) or set(base['env']) - set(env):
        raise ValueError('Unknown or missing environment options')
    for key, value in env.items():
        if value not in ENV_VALUES.get(key, {base['env'].get(key)}):
            raise ValueError(f'Unapproved environment option: {key}={value}')
    options = dict(zip(args[::2], args[1::2]))
    if options['--mmap-experts'] == 'off' and cfg.get('require_full_copies') is not True:
        raise ValueError('RAM timing requires verified full expert copies')
    flow_keys = {'DS4_TP_GGUF_UNEVEN', 'DS4_FLOW_TP', 'DS4_FLOW_PUMP_WAIT', 'DS4_TP_CHECK'}
    if flow_keys & set(env):
        if (env.get('DS4_FLOW_TP') != '1' or env.get('DS4_TP_GGUF_UNEVEN') != '1' or
                env.get('DS4_FLOW_PUMP_WAIT') not in ('0', '1')):
            raise ValueError('Flow needs explicit whole-block TP and pump settings')
        if env['STRATA_DS4_PROMPT_SKIP'] != '0' or options['--mmap-experts'] != 'off':
            raise ValueError('Screen flow separately: YOCO off, verified full RAM copies required')
    return {'policy': POLICY, 'timing_eligible': True,
            'prompt_skip': env['STRATA_DS4_PROMPT_SKIP'],
            'flow_tp': env.get('DS4_FLOW_TP', '0'),
            'quality_and_long_context_validated': False,
            'bit_exact_required': False}


def engine_env(cfg, inherited):
    validate_config(cfg)
    # Public names are aliases translated by maya.py, not by the native engine.
    # Clear both spellings, including unlisted test knobs such as YOCO_KEEP.
    return {k: v for k, v in inherited.items()
            if not k.startswith(('DS4_', 'STRATA_DS4_', 'MAYA_DS4_'))} | cfg['env']


def validate_limits(state):
    if state.get('cpu.max', '').split()[:1] != ['max']:
        raise ValueError('Full-compute timing requires no CPU quota')
    limit = state.get('memory.max', 'max')
    if not limit.isdecimal() or not 0 < int(limit) <= 192 * 2**30:
        raise ValueError('A finite host memory cap of at most 192Gi is required')


def runtime_configs():
    configs = {}
    for threads, parts, chunk in ((48, 1, 2048), (56, 1, 2048), (56, 2, 2048),
                                   (56, 1, 4096), (56, 2, 4096)):
        cfg = copy.deepcopy(baseline())
        name = f'copy-c{threads}-numa{parts}-p{chunk}'
        cfg.update(name=name, policy=POLICY, require_full_copies=True)
        for key, value in (('--cpu-threads', threads), ('--prefill-chunk', chunk),
                           ('--mmap-experts', 'off')):
            cfg['args'][cfg['args'].index(key) + 1] = str(value)
        cfg['env']['DS4_COPY_NUMA'] = str(parts)
        validate_config(cfg)
        configs[name] = cfg
    return configs


def validate_cases(rows):
    if len(rows) != 18 or [r['phase'] for r in rows[:12]] != ['warmup'] * 12:
        raise ValueError('Expected 12 warmups followed by six development requests')
    if [r['phase'] for r in rows[12:]] != ['dev'] * 6:
        raise ValueError('Holdout data must not be used for tuning')
    if [r['pp'] for r in rows] != [2048] * 12 + [2048, 4096, 8192] * 2:
        raise ValueError('Unexpected frozen prompt lengths')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate case IDs')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', type=Path, required=True, help='Existing frozen development history')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--run', action='store_true', help='Run on explicitly approved GPU hardware')
    a = p.parse_args()
    data = a.cases.read_bytes()
    validate_cases([json.loads(s) for s in data.splitlines() if s.strip()])
    configs = runtime_configs()
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out / 'configs').mkdir()
    (a.out / 'cases.jsonl').write_bytes(data)
    eligibility = {}
    for name, cfg in configs.items():
        path = a.out / 'configs' / f'{name}.json'
        path.write_text(json.dumps(cfg, indent=2) + '\n')
        eligibility[name] = validate_config(cfg) | {
            'config_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    control = next(iter(configs))
    order = [(name, name) for name in configs] + [('control-repeat', control)]
    plan = {'policy': POLICY, 'cases_sha256': hashlib.sha256(data).hexdigest(),
            'run_order': order, 'eligibility': eligibility,
            'historical_strict_verdicts_unchanged': True}
    (a.out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    if not a.run:
        return
    for output, name in order:
        subprocess.run([sys.executable, str(ROOT / 'native_bench.py'),
                        '--config', str(a.out / 'configs' / f'{name}.json'),
                        '--cases', str(a.out / 'cases.jsonl'), '--out', str(a.out / output)],
                       check=True)
    with (a.out / 'summary.json').open('x') as out:
        subprocess.run([sys.executable, str(ROOT / 'summary.py'),
                        *(str(a.out / output) for output, _ in order)], stdout=out, check=True)


if __name__ == '__main__':
    main()
