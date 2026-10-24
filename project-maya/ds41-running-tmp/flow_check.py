#!/usr/bin/env python3
"""Bounded TP/flow screening; numerical/byte checks, not a warm speed claim."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from full_compute import validate_config
from native_bench import emit_event


def check_log(log, prompt_tokens=None):
    activation = re.findall(r'tensor-parallel members on the prompt path.s flow: (.*?) -', log)
    active = {int(v) for line in activation for v in re.findall(r'CUDA(\d+)', line)}
    stream_pattern = r'ds4 prompt stream, CUDA(\d+):'
    if prompt_tokens is not None:
        stream_pattern += rf' {prompt_tokens} tokens\b'
    streamed = {int(v) for v in re.findall(stream_pattern, log)}
    copies = re.findall(r"the flow's copies passed \((\d+) of the formats'", log)
    n = int(copies[-1]) if copies else 0
    guarded = len(re.findall(r'guards intact \(DS4_FLOW_TP\)', log))
    numerical = bool(re.search(r'TP check passed \([1-9]\d* expert formats and rotations', log))
    errors = bool(re.search(r'TP check.*(?:FAILED|TOO FAR|state unknown)', log))
    return {'active_devices': sorted(active), 'streamed_devices': sorted(streamed),
            'flow_copy_checks': n, 'guarded_copy_checks': guarded,
            'native_tp_numerical_check_passed': numerical,
            'passed': active == streamed == {0, 1, 2, 3} and n > 0 and guarded >= n and numerical and not errors,
            'diagnostic_not_warm_timing': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--cases', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--timeout', type=int, default=600)
    a = p.parse_args()
    cfg = json.loads(a.config.read_text())
    validate_config(cfg)
    if cfg['env'].get('DS4_TP_CHECK') != '1' or '--verbose' not in cfg['args']:
        raise ValueError('Flow diagnostic requires native TP checks and activation logs')
    rows = [json.loads(s) for s in a.cases.read_text().splitlines() if s.strip()]
    if len(rows) != 2 or [r['pp'] for r in rows] != [2048, 4096]:
        raise ValueError('Flow screen is bounded to two frozen PP2048/4096 requests')
    result = subprocess.run([sys.executable, str(Path(__file__).with_name('native_bench.py')),
                             '--config', str(a.config), '--cases', str(a.cases), '--out', str(a.out),
                             '--timeout', str(a.timeout), '--dump'])
    if result.returncode:
        # No second launch after an engine error, especially an unknown-device exit.
        raise SystemExit(result.returncode if result.returncode > 0 else 1)
    verdict = check_log((a.out / 'engine.log').read_text())
    (a.out / 'verdict.json').write_text(json.dumps(verdict, indent=2) + '\n')
    emit_event('verdict', verdict)
    print(json.dumps(verdict, indent=2), flush=True)
    if not verdict['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
