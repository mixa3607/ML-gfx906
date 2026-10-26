#!/usr/bin/env python3
"""Two cache-local code starts, then one independently seeded Russian full suite."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sys
import threading
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from screen import Engine, parse_done, sha, snapshot
from stream import artifact, checkpoint, progress, write_json

ROOT = Path('/data/screen')
INPUT = Path(__file__).resolve().parent
SESSIONS = (('code-1', 'code-cases.jsonl', 24), ('code-2', 'code-cases.jsonl', 24),
            ('russian', 'russian-cases.jsonl', 18))
PROFILE_SHA = 'bcfd7697fc070b0ebcb0138c0ef029429ea0d4ff81ca60eeb7804e08efd0cd29'
SOURCE = '6afa525bbabc3a8f5fd165f89e9bc72155d9bd39'


def validate(row, expected_pp):
    d = row['done']
    if d['pp'] != expected_pp or d['reused']:
        raise ValueError('Truncated input or cross-request reuse')
    if d['tg'] != len(row['tokens']) or not 1 <= d['tg'] <= 256:
        raise ValueError('Inconsistent output token count')
    if not 0 <= d['accepted'] <= d['drafted']:
        raise ValueError('Invalid draft counters')
    if any(not math.isfinite(d[k]) or d[k] <= 0 for k in ('prompt_ms', 'decode_ms')):
        raise ValueError('Invalid native timing')
    if any(float(s.get('skipped', 0)) for s in row['stats']):
        raise ValueError('Approximate expert skips reported')
    if row['before']['memory.events']['oom_kill'] != row['after']['memory.events']['oom_kill']:
        raise ValueError('OOM during request')
    if row['before']['cpu.stat']['nr_throttled'] != row['after']['cpu.stat']['nr_throttled']:
        raise ValueError('CPU throttling')


class BenchEngine(Engine):
    def request(self, case):
        before = snapshot(self.proc.pid)
        start = time.monotonic()
        message = 'GEN 256 temperature=0 seed=1 spec=1 dspark_conf=0.5 dspark_cum=0.5 '
        self.proc.stdin.write((message + ','.join(map(str, case['ids'])) + '\n').encode())
        self.proc.stdin.flush()
        tokens, times, stats = [], [], []
        while True:
            line = self.line(start + 1800)
            now = time.monotonic()
            if line.startswith('T '):
                tokens.append(int(line.split()[1]))
                times.append(now - start)
            elif line.startswith('STAT '):
                stats.append(dict(p.split('=', 1) for p in line.split()[1:]))
            elif line.startswith('ERR '):
                raise RuntimeError(line)
            elif line.startswith('DONE '):
                done = parse_done(line)
                break
        elapsed = time.monotonic() - start
        row = {'id': case['id'], 'phase': case['phase'], 'lead_title': case['lead_title'],
               'expected_pp': len(case['ids']), 'done': done, 'wall_s': elapsed,
               'ttft_s': times[0] if times else None, 'token_delivery_s': times,
               'tokens': tokens, 'stats': stats, 'before': before, 'after': snapshot(self.proc.pid),
               'output_ids_sha256': hashlib.sha256(json.dumps(tokens).encode()).hexdigest()}
        row['pp_tok_s'] = 1000 * done['pp'] / done['prompt_ms'] if done['prompt_ms'] else None
        row['decode_tok_s'] = 1000 * (done['tg'] - 1) / done['decode_ms'] if done['decode_ms'] else None
        validate(row, len(case['ids']))
        row['complete_tg256'] = done['tg'] == 256 and done['finish'] == 'length'
        row['valid'] = row['complete_tg256']
        if not row['valid']:
            row['error'] = 'Natural EOS/incomplete TG256; retained, not replaced or extended'
        return row


def pooled(rows):
    if not rows or not all(r['valid'] for r in rows):
        raise ValueError('Cannot pool incomplete samples')
    d = [r['done'] for r in rows]
    offered, accepted = sum(x['drafted'] for x in d), sum(x['accepted'] for x in d)
    lookups, hits = sum(x['lookups'] for x in d), sum(x['hits'] for x in d)
    return {'requests': len(rows), 'prefill_tok_s': sum(x['pp'] for x in d) / sum(x['prompt_ms'] / 1000 for x in d),
            'decode_tok_s': sum(x['tg'] - 1 for x in d) / sum(x['decode_ms'] / 1000 for x in d),
            'wall_s': sum(r['wall_s'] for r in rows), 'ttft_s': [r['ttft_s'] for r in rows],
            'drafted': offered, 'accepted': accepted, 'acceptance': accepted / offered if offered else None,
            'accepted_per_generated': accepted / sum(x['tg'] for x in d),
            'expert_hits': hits, 'expert_lookups': lookups, 'expert_hit_ratio': hits / lookups if lookups else None}


def case_check(cases, filename):
    warm = 12
    expected = [2048] * warm + ([2048] * 12 if filename == 'code-cases.jsonl' else [2048, 4096, 8192] * 2)
    if [len(c['ids']) for c in cases] != expected:
        raise ValueError('Unexpected PP schedule')
    if [c['phase'] for c in cases] != ['warmup'] * warm + ['measurement'] * (len(cases) - warm):
        raise ValueError('Unexpected warmup/measurement phases')
    unique = len({tuple(c['ids']) for c in cases})
    if unique != (1 if filename == 'code-cases.jsonl' else 18):
        raise ValueError('Wrong intentional-repeat or distinct-prose workload')


def run_session(base, name, filename, expected):
    sys.path[:0] = ['/opt/maya', '/opt/maya/tools']
    from strata_tokenizer import Tokenizer
    tokenizer = Tokenizer.from_dir(base['tokenizer'])
    out = ROOT / name
    out.mkdir()
    cases = [json.loads(s) for s in (INPUT / filename).read_text().splitlines()]
    case_check(cases, filename)
    profile = out / 'expert-profile.bin'
    shutil.copyfile(ROOT / 'seed-profile.bin', profile)
    if sha(profile) != PROFILE_SHA:
        raise ValueError('Original profile seed changed')
    config = json.loads(json.dumps(base))
    config['args'][config['args'].index('--expert-profile') + 1] = str(profile)
    config['log'] = str(out / 'engine.log')
    write_json(out / 'config.json', config)
    record = {'name': name, 'cases_sha256': sha(INPUT / filename), 'seed_profile_sha256': sha(profile),
              'source_commit': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
              'build': json.loads(Path('/opt/maya/build-hip/MAYA-BUILD.json').read_text()),
              'before': snapshot(), 'stage': 'starting', 'complete': False, 'expected_results': expected}
    write_json(out / 'manifest.json', record)
    checkpoint(name + '-starting')
    engine, rows = None, []
    try:
        if (record['before']['memory.max'] != str(220 * 2**30) or
                not record['before']['cpu.max'].startswith('max ') or record['source_commit'] != SOURCE):
            raise ValueError('Unexpected memory cap, CPU quota or source revision')
        inherited = {k: v for k, v in os.environ.items()
                     if not k.startswith(('DS4_', 'STRATA_', 'MAYA_', 'HSA_OVERRIDE_'))}
        config['env'] = inherited | config['env']
        started = time.monotonic()
        engine = BenchEngine(config, out)
        record['ready'] = engine.ready()
        record['load_s'] = time.monotonic() - started
        engine.copies_logged.wait(5)
        log = (out / 'engine.log').read_text()
        copies = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM", log)
        if not copies or copies[1] != copies[2] or 'DS4_DRAFT_DEV 1,2,3' not in log:
            raise ValueError('Incomplete expert copies or wrong drafter placement')
        record['full_copies'] = list(map(int, copies.groups()))
        vram = [dict(s.split('=', 1) for s in line.split()[1:] if '=' in s)
                for line in record['ready'] if line.startswith('VRAM ')]
        if (len(vram) != 4 or any(v.get('tp_n') != '4' or v.get('ctx') != '196608' for v in vram)
                or not any('vision=ds4 ' in line for line in record['ready'])):
            raise ValueError('TP4/context196608/vision not verified')
        record.update(stage='ready', ready_snapshot=snapshot(engine.proc.pid))
        write_json(out / 'manifest.json', record)
        checkpoint(name + '-ready')
        progress(f'READY {name}: {record["load_s"]:.1f}s')
        for case in cases:
            row = engine.request(case)
            row['output_text'] = b''.join(tokenizer.token_bytes(t) for t in row['tokens']).decode('utf-8', errors='replace')
            text = json.dumps(row, ensure_ascii=False) + '\n'
            with (out / 'results.jsonl').open('a') as f:
                f.write(text)
                f.flush()
            artifact(out / 'results.jsonl', text, append=True)
            checkpoint(name + '-' + case['id'] + '-result')
            rows.append(row)
            progress({'session': name, 'case': row['id'], 'pp': row['done']['pp'], 'tg': row['done']['tg'],
                      'decode_tok_s': row['decode_tok_s'], 'valid': row['valid']})
        record.update(stage='complete', executed=True,
                      complete=len(rows) == expected and all(r['valid'] for r in rows))
        scored = [r for r in rows if r['phase'] == 'measurement']
        if record['complete']:
            record['metrics'] = pooled(scored)
            record['by_pp'] = {str(pp): pooled([r for r in scored if r['done']['pp'] == pp])
                               for pp in sorted({r['done']['pp'] for r in scored})}
        record['actual_tg'] = [r['done']['tg'] for r in rows]
        record['unique_scored_output_hashes'] = len({r['output_ids_sha256'] for r in scored})
    except Exception:
        record.update(stage='error', error=traceback.format_exc())
        progress(record['error'])
    finally:
        if engine:
            engine.close()
        record['after'] = snapshot()
        if (record['before']['memory.events']['oom_kill'] != record['after']['memory.events']['oom_kill'] or
                record['before']['cpu.stat']['nr_throttled'] != record['after']['cpu.stat']['nr_throttled']):
            record.update(complete=False, error='Session OOM/CPU throttling')
        record['saved_results'] = len(rows)
        write_json(out / 'manifest.json', record)
        checkpoint(name + '-finished')
    return record


def main():
    if os.environ.get('BENCH_STREAM') != '1':
        raise RuntimeError('Acknowledged durable collector is mandatory')
    base = json.loads((INPUT / 'runtime.json').read_text())
    frozen = json.loads((INPUT / 'cases.manifest.json').read_text())
    for name, digest in frozen['files'].items():
        if sha(INPUT / name) != digest:
            raise ValueError('Frozen input hash mismatch: ' + name)
    source_paths = {'bench.py': INPUT / 'bench.py', 'screen.py': INPUT.parent / 'screen.py',
                    'stream.py': INPUT.parent / 'stream.py'}
    experiment = {'sessions': [list(s) for s in SESSIONS], 'inputs': frozen,
                  'runtime_sha256': sha(INPUT / 'runtime.json'),
                  'sources': {name: sha(p) for name, p in source_paths.items()}}
    write_json(ROOT / 'experiment.json', experiment)
    checkpoint('experiment')
    stop = threading.Event()
    current = {'session': None}

    def heartbeat():
        while not stop.wait(15):
            text = json.dumps(current | {'snapshot': snapshot()}) + '\n'
            with (ROOT / 'heartbeat.jsonl').open('a') as f:
                f.write(text)
            artifact(ROOT / 'heartbeat.jsonl', text, append=True)

    monitor = threading.Thread(target=heartbeat, daemon=True)
    monitor.start()
    records = []
    try:
        for name, filename, expected in SESSIONS:
            current['session'] = name
            record = run_session(base, name, filename, expected)
            records.append(record)
            write_json(ROOT / 'summary.json', {'complete': False, 'sessions': records})
            checkpoint(name + '-summary')
            if record['stage'] == 'error':
                break
    finally:
        stop.set()
        monitor.join(5)
    summary = {'complete': len(records) == 3 and all(r['complete'] for r in records),
               'sessions': records, 'saved_results': sum(r['saved_results'] for r in records)}
    if len(records) >= 2 and records[0]['complete'] and records[1]['complete']:
        summary['code_fresh_repeat_decode_delta_pct'] = 100 * (
            records[1]['metrics']['decode_tok_s'] / records[0]['metrics']['decode_tok_s'] - 1)
    write_json(ROOT / 'summary.json', summary)
    checkpoint('suite-finished')
    raise SystemExit(0 if summary['complete'] else 2)


if __name__ == '__main__':
    main()
