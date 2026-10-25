#!/usr/bin/env python3
"""Bounded genuine TP4 diagnostic; reject fallback and missing numerical checks."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

from full_compute import validate_config
from native_bench import emit_event


def check_log(log):
    summary = re.findall(r'TP check passed \(([1-9]\d*) expert formats and rotations', log)
    members = [int(v) for v in re.findall(r'(\d+) members. parts summed against the whole', log)]
    errors = bool(re.search(r'TP check.*(?:FAILED|TOO FAR|state unknown)', log))
    n = int(summary[-1]) if summary else 0
    return {'native_tp_numerical_check_passed': n > 0,
            'formats_and_rotations': n, 'member_sum_checks': len(members),
            'members_per_check': sorted(set(members)),
            'passed': n > 0 and len(members) >= n and set(members) == {4} and not errors,
            'diagnostic_not_warm_timing': True}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--cases', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--timeout', type=int, default=600)
    a = p.parse_args()
    cfg = json.loads(a.config.read_text())
    policy = validate_config(cfg)
    if policy['requested_tp'] != 4 or cfg['env'].get('DS4_TP_CHECK') != '1' or '--verbose' not in cfg['args']:
        raise ValueError('TP4 screen requires TP4, native TP checks and verbose logs')
    rows = [json.loads(s) for s in a.cases.read_text().splitlines() if s.strip()]
    if len(rows) != 2 or [r['pp'] for r in rows] != [2048, 4096]:
        raise ValueError('TP4 screen is bounded to the frozen PP2048/4096 requests')
    code = subprocess.run([sys.executable, str(Path(__file__).with_name('native_bench.py')),
                           '--config', str(a.config), '--cases', str(a.cases), '--out', str(a.out),
                           '--timeout', str(a.timeout), '--dump']).returncode
    if code:
        raise SystemExit(code if code > 0 else 1)
    verdict = check_log((a.out / 'engine.log').read_text())
    verdict['topology'] = json.loads((a.out / 'ready.json').read_text())['topology']
    verdict['passed'] = verdict['passed'] and verdict['topology']['verified']
    (a.out / 'verdict.json').write_text(json.dumps(verdict, indent=2) + '\n')
    emit_event('verdict', verdict)
    print(json.dumps(verdict, indent=2), flush=True)
    if not verdict['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
