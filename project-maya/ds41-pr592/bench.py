#!/usr/bin/env python3
"""One warmed TP2 context sweep in a persistent native DSpark engine."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import traceback

from startup import Engine, snapshot, write_json


def parse_done(line):
    p = line.split()
    if len(p) != 11 or p[0] != 'DONE':
        raise ValueError(f'Unexpected DONE: {line}')
    return dict(tg=int(p[1]), pp=int(p[2]), prompt_ms=float(p[3]), decode_ms=float(p[4]),
                finish=p[5], accepted=int(p[6]), drafted=int(p[7]), reused=int(p[8]),
                hits=int(p[9]), lookups=int(p[10]))


def counters(text):
    return {k: int(v) for k, v in (line.split() for line in text.splitlines())}


def validate(row, expected_pp):
    d = row['done']
    if d['pp'] != expected_pp or d['reused']:
        raise ValueError('Truncated input or cross-request KV reuse')
    if d['tg'] != len(row['tokens']) or not 1 <= d['tg'] <= 256:
        raise ValueError('Invalid generated token count')
    if not 0 <= d['accepted'] <= d['drafted'] or d['finish'] not in ('stop', 'length'):
        raise ValueError('Invalid draft counters or finish reason')
    if (not math.isfinite(d['prompt_ms']) or d['prompt_ms'] <= 0 or
            not math.isfinite(d['decode_ms']) or d['decode_ms'] < 0 or
            (d['tg'] > 1 and d['decode_ms'] == 0)):
        raise ValueError('Invalid native timing')
    if any(float(s.get('skipped', 0)) for s in row['stats']):
        raise ValueError('Approximate computation skip')
    for name, key in (('memory.events', 'oom_kill'), ('cpu.stat', 'nr_throttled')):
        if counters(row['before'][name])[key] != counters(row['after'][name])[key]:
            raise ValueError(f'{key} changed during the request')


def request(engine, case):
    row = {k: case[k] for k in ('id', 'phase', 'ctx', 'pp', 'prompt_sha256')}
    row['before'] = snapshot()
    started = time.monotonic()
    engine.proc.stdin.write(('GEN 256 temperature=0 seed=1 spec=1 dspark_conf=0.5 dspark_cum=0.5 '
                             + ','.join(map(str, case['ids'])) + '\n').encode())
    engine.proc.stdin.flush()
    tokens, times, stats = [], [], []
    while True:
        line = engine.line(started + 1800)
        if line.startswith('T '):
            tokens.append(int(line.split()[1]))
            times.append(time.monotonic() - started)
        elif line.startswith('STAT '):
            stats.append(dict(p.split('=', 1) for p in line.split()[1:]))
        elif line.startswith('DONE '):
            row['done'] = parse_done(line)
            break
    row.update(tokens=tokens, token_delivery_s=times, stats=stats,
               wall_s=time.monotonic() - started, after=snapshot())
    try:
        validate(row, len(case['ids']))
    except ValueError as error:
        row['validation_error'] = str(error)
    row['complete_tg256'] = row['done']['tg'] == 256 and row['done']['finish'] == 'length'
    row['pp_tok_s'] = 1000 * row['done']['pp'] / row['done']['prompt_ms']
    row['native_decode_tok_s'] = (1000 * (row['done']['tg'] - 1) / row['done']['decode_ms']
                                if row['done']['decode_ms'] > 0 else None)
    row['ttft_s'] = times[0] if times else None
    row['output_ids_sha256'] = hashlib.sha256(json.dumps(tokens).encode()).hexdigest()
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--name', required=True)
    ap.add_argument('--peer', action='store_true')
    args = ap.parse_args()
    root = Path(__file__).resolve().parent
    out = Path('/data') / args.name
    out.mkdir()
    config = json.loads((root / 'runtime.json').read_text())
    profile = out / 'expert-profile.bin'
    shutil.copyfile('/data/seed-profile.bin', profile)
    config['args'][config['args'].index('--expert-profile') + 1] = str(profile)
    config['env']['DS4_HIP_PEER_AR'] = '1' if args.peer else '0'
    config['env']['DS4_LANE_CAL'] = str(out / 'lane-times.txt')
    write_json(out / 'config.json', config)
    frozen = json.loads((root / 'cases.manifest.json').read_text())
    for name, digest in frozen['files'].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Frozen file changed: {name}')
    record = {'name': args.name, 'peer_requested': args.peer, 'complete': False,
              'before': snapshot(), 'source_commit': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
              'seed_profile_sha256': hashlib.sha256(profile.read_bytes()).hexdigest(),
              'cases_sha256': frozen['files']['cases.jsonl']}
    write_json(out / 'manifest.json', record)
    engine, rows = None, []
    try:
        expected_source = ('9a0876f5861de25f4cb56b7e19e1c8b63704dcda' if args.peer
                           else 'b04264526e93a3c7d3c051cb9cec97af86ae8a37')
        if record['source_commit'] != expected_source:
            raise ValueError('Wrong source revision')
        if record['before']['memory.max'] != str(220 * 2**30) or not record['before']['cpu.max'].startswith('max '):
            raise ValueError('Wrong memory limit or CPU quota')
        started = time.monotonic()
        engine = Engine(config, out)
        record['ready'] = engine.ready()
        record['load_s'] = time.monotonic() - started
        vram = [dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)
                for line in record['ready'] if line.startswith('VRAM ')]
        if len(vram) != 4 or any(v.get('tp_n') != '2' or v.get('ctx') != '196608' for v in vram):
            raise ValueError('Four GPUs / TP2 / context196608 not confirmed')
        log = (out / 'engine.log').read_text()
        enabled = log.count('exact peer prefill all-reduce enabled')
        record['peer_groups_enabled'] = enabled
        if enabled != (2 if args.peer else 0):
            raise ValueError('Requested peer transport not active on both groups, or baseline unexpectedly active')
        write_json(out / 'manifest.json', record)
        cases = [json.loads(s) for s in (root / 'cases.jsonl').read_text().splitlines()]
        if [c['pp'] for c in cases] != [2048] * 12 + [4096, 8192, 16384] * 2 + [1, 1]:
            raise ValueError('Wrong context schedule')
        with (out / 'results.jsonl').open('x') as f:
            for case in cases:
                row = request(engine, case)
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                rows.append(row)
                print(json.dumps({k: row[k] for k in ('id', 'phase', 'ctx', 'done', 'complete_tg256')}), flush=True)
                if row.get('validation_error'):
                    raise ValueError(row['validation_error'])
        record['complete'] = len(rows) == 20 and all(r['complete_tg256'] for r in rows)
        record['executed'] = True
    except Exception:
        record['error'] = traceback.format_exc()
    finally:
        if engine:
            engine.close()
        record['saved_results'] = len(rows)
        record['after'] = snapshot()
        write_json(out / 'manifest.json', record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    return 0 if record.get('executed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
