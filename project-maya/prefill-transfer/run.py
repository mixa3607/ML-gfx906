#!/usr/bin/env python3
"""Bounded native timing/diagnostics; stream evidence to an acknowledged collector."""
import argparse
from array import array
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path('/data/runs')
LOCK = threading.Lock()


def emit(kind, **data):
    with LOCK:
        print('BENCH_EVENT ' + json.dumps({'kind': kind, **data}), flush=True)


def artifact(path, data, append=False):
    emit('artifact', path=str(path.relative_to(ROOT)), data=data, append=append)


def save(path, data):
    text = json.dumps(data, indent=2) + '\n'
    path.write_text(text)
    artifact(path, text)


def checkpoint(label):
    emit('checkpoint', label=label)
    if sys.stdin.readline().strip() != 'ACK ' + label:
        raise RuntimeError('Durable collector disconnected')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot():
    root = Path('/sys/fs/cgroup')
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::') and (root / line[3:].lstrip('/') / 'memory.current').exists():
            root /= line[3:].lstrip('/')
    data = {k: (root / k).read_text().strip() for k in
            ('memory.current', 'memory.peak', 'memory.max', 'cpu.max', 'cpuset.cpus.effective')}
    for k in ('memory.stat', 'memory.events', 'cpu.stat'):
        data[k] = {a: int(b) for a, b in (s.split() for s in (root / k).read_text().splitlines())}
    return data | {'unix': time.time()}


def parse_done(line):
    p = line.split()
    if len(p) != 11 or p[0] != 'DONE':
        raise ValueError('Unexpected native DONE: ' + line)
    return dict(tg=int(p[1]), pp=int(p[2]), prompt_ms=float(p[3]), decode_ms=float(p[4]),
                finish=p[5], accepted=int(p[6]), drafted=int(p[7]), reused=int(p[8]),
                hits=int(p[9]), lookups=int(p[10]))


def pooled(rows):
    if not rows or not all(r['valid'] for r in rows):
        raise ValueError('Incomplete samples cannot be pooled')
    d = [r['done'] for r in rows]
    return {'requests': len(rows),
            'prefill_tok_s': sum(x['pp'] for x in d) * 1000 / sum(x['prompt_ms'] for x in d),
            'decode_tok_s': sum(x['tg'] - 1 for x in d) * 1000 / sum(x['decode_ms'] for x in d),
            'wall_s': sum(r['wall_s'] for r in rows),
            'accepted': sum(x['accepted'] for x in d), 'drafted': sum(x['drafted'] for x in d)}


class Engine:
    def __init__(self, config, out):
        self.out = out
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('DS4_', 'STRATA_', 'MAYA_', 'HSA_OVERRIDE_'))}
        env.update(config['env'])
        self.proc = subprocess.Popen([config['exe'], *config['args'], '--serve'],
                                     cwd=config['cwd'], env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.buffer = b''
        self.logs = []
        self.thread = threading.Thread(target=self.capture, daemon=True)
        self.thread.start()

    def capture(self):
        with (self.out / 'engine.log').open('w') as log:
            for raw in self.proc.stderr:
                text = raw.decode('utf-8', errors='replace')
                self.logs.append(text)
                log.write(text)
                log.flush()
                artifact(self.out / 'engine.log', text, True)

    def line(self, deadline):
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise TimeoutError('Native engine deadline exceeded')
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError(f'Native engine exited: {self.proc.poll()}')
            self.buffer += chunk
            artifact(self.out / 'protocol.log', chunk.decode('utf-8', errors='replace'), True)
        raw, self.buffer = self.buffer.split(b'\n', 1)
        line = raw.decode('utf-8', errors='replace')
        if line.startswith('ERR '):
            raise RuntimeError(line)
        return line

    def ready(self):
        lines, deadline = [], time.monotonic() + 1800
        while True:
            line = self.line(deadline)
            lines.append(line)
            if line.startswith('READY '):
                return lines

    def request(self, case, diagnostic):
        start = time.monotonic()
        tg = 16 if diagnostic else 256
        message = f'GEN {tg} temperature=0 seed=1 spec={int(not diagnostic)} dspark_conf=0.5 dspark_cum=0.5 '
        self.proc.stdin.write((message + ','.join(map(str, case['ids'])) + '\n').encode())
        self.proc.stdin.flush()
        tokens, times, stats = [], [], []
        while True:
            line = self.line(start + 1800)
            if line.startswith('T '):
                tokens.append(int(line.split()[1]))
                times.append(time.monotonic() - start)
            elif line.startswith('STAT '):
                stats.append(dict(s.split('=', 1) for s in line.split()[1:]))
            elif line.startswith('DONE '):
                done = parse_done(line)
                break
        if done['pp'] != len(case['ids']) or done['reused'] or done['tg'] != len(tokens):
            raise ValueError('Truncated input, cross-request reuse or inconsistent output')
        if any(not math.isfinite(done[k]) or done[k] <= 0 for k in ('prompt_ms', 'decode_ms')):
            raise ValueError('Invalid native timings')
        if any(float(s.get('skipped', 0)) for s in stats):
            raise ValueError('Approximate computation skipping')
        return {'id': case['id'], 'phase': 'diagnostic' if diagnostic else case['phase'],
                'done': done, 'tokens': tokens, 'stats': stats, 'token_delivery_s': times,
                'ttft_s': times[0] if times else None, 'wall_s': time.monotonic() - start,
                'valid': bool(tokens) and (diagnostic or done['tg'] == 256 and done['finish'] == 'length')}

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write(b'STOP\nQUIT\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=90)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                if self.proc.poll() is None:
                    os.killpg(self.proc.pid, signal.SIGTERM)
                    try:
                        self.proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(self.proc.pid, signal.SIGKILL)
                        self.proc.wait()
        self.thread.join(15)
        self.selector.close()
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            pipe.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--transfer', action='store_true')
    parser.add_argument('--pin-off', action='store_true')
    parser.add_argument('--prune', action='store_true')
    parser.add_argument('--chunk', type=int, choices=(2048, 4096), default=2048)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+', args.name):
        raise ValueError('Unsafe session name')
    out = ROOT / args.name
    out.mkdir(parents=True, exist_ok=False)
    source = Path('/data/input')
    config = json.loads((source / 'runtime.json').read_text())
    seed = out / 'expert-profile.bin'
    shutil.copyfile(source / 'seed-profile.bin', seed)
    config['args'][config['args'].index('--expert-profile') + 1] = str(seed)
    config['args'][config['args'].index('--prefill-chunk') + 1] = str(args.chunk)
    config['env']['DS4_SKIP_UNPICKED'] = str(int(args.prune))
    if args.pin_off:
        config['env']['DS4_COPY_PIN'] = '0'
    if args.diagnostic:
        config['args'].append('--no-expert-cache')
        config['env'].update(DS4_TP_CHECK='1', DS4_CHECK_SWAPS='1', DS4_PROF='1',
                             DS4_PREFILL_STATS='1', DS4_FLOW_STATS='1',
                             DS4_SERVE_DUMP=str(out / 'logits'))
    save(out / 'config.json', config)
    cases = [json.loads(s) for s in (source / 'cases.jsonl').read_text().splitlines()]
    if [len(c['ids']) for c in cases] != [2048] * 12 + [2048, 4096, 8192] * 2:
        raise ValueError('Unexpected frozen workload')
    record = {'arguments': vars(args), 'before': snapshot(), 'seed_sha256': sha(seed),
              'cases_sha256': sha(source / 'cases.jsonl'), 'runner_sha256': sha(Path(__file__)),
              'source': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
              'model_files': {p: sha(Path('/data/ds4') / p) for p in ('ds4.txt', 'tensors.txt')},
              'complete': False}
    if record['source'] != '8621e33159f426da2d376be4ec012b0ce8fe2948':
        raise ValueError('Unexpected engine source revision')
    save(out / 'manifest.json', record)
    checkpoint(args.name + '-starting')
    if record['before']['memory.max'] != str(220 * 2**30) or not record['before']['cpu.max'].startswith('max '):
        raise ValueError('Wrong memory cap or CPU quota')
    engine, rows = None, []
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(15):
            emit('progress', value={'name': args.name, 'memory': snapshot()})

    monitor = threading.Thread(target=heartbeat, daemon=True)
    monitor.start()
    try:
        start = time.monotonic()
        engine = Engine(config, out)
        record['ready'] = engine.ready()
        record['load_s'] = time.monotonic() - start
        log = ''.join(engine.logs)
        copies = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM", log)
        if not copies or copies[1] != copies[2] or 'DS4_DRAFT_DEV 1,2,3' not in log:
            raise ValueError('Incomplete RAM expert copies or wrong DSpark placement')
        vram = [dict(s.split('=', 1) for s in line.split()[1:] if '=' in s)
                for line in record['ready'] if line.startswith('VRAM ')]
        if len(vram) != 4 or any(v.get('tp_n') != '4' or v.get('ctx') != '196608' for v in vram):
            raise ValueError('Actual TP4/context not verified')
        if not any('vision=ds4 ' in line for line in record['ready']):
            raise ValueError('Native vision not loaded')
        if args.transfer:
            if args.diagnostic and "the prompt path's copies passed" not in log:
                raise ValueError('Transfer byte checker did not execute')
            if not args.pin_off and 'the prompt path DMAs them in place' not in log:
                raise ValueError('Direct RAM DMA did not activate')
        record['full_copies'] = list(map(int, copies.groups()))
        save(out / 'manifest.json', record)
        checkpoint(args.name + '-ready')
        selected = [cases[12], cases[13]] if args.diagnostic else cases
        for i, case in enumerate(selected, 1):
            row = engine.request(case, args.diagnostic)
            row['snapshot'] = snapshot()
            if args.diagnostic:
                path = out / f'logits.{i}.f32'
                values = array('f')
                values.frombytes(path.read_bytes())
                if not values or any(not math.isfinite(x) for x in values):
                    raise ValueError('Missing or nonfinite diagnostic logits')
                row['logits'] = {'sha256': sha(path), 'floats': len(values),
                                 'max_abs': max(abs(x) for x in values)}
                vocab = len(json.loads(Path(config['tokenizer'], 'vocab.json').read_text()))
                if len(values) < vocab or len(values) % vocab:
                    raise ValueError('Invalid full-vocabulary logits dimensions')
                row['logits']['vocab'] = vocab
                # The first row is the same full-prefill input in every diagnostic arm.
                row['logits']['first_row_sha256'] = hashlib.sha256(values[:vocab].tobytes()).hexdigest()
            rows.append(row)
            text = json.dumps(row) + '\n'
            with (out / 'results.jsonl').open('a') as f:
                f.write(text)
            artifact(out / 'results.jsonl', text, True)
            checkpoint(args.name + '-' + case['id'] + '-result')
            emit('progress', value={'name': args.name, 'case': case['id'], 'done': row['done'], 'valid': row['valid']})
        record['complete'] = all(r['valid'] for r in rows)
        if not args.diagnostic and record['complete']:
            scored = [r for r in rows if r['phase'] == 'measurement']
            record['metrics'] = pooled(scored)
            record['by_pp'] = {str(pp): pooled([r for r in scored if r['done']['pp'] == pp])
                               for pp in (2048, 4096, 8192)}
    except Exception:
        record['error'] = traceback.format_exc()
        emit('progress', value=record['error'])
    finally:
        if engine:
            engine.close()
        stop.set()
        monitor.join(5)
        record['after'] = snapshot()
        if any(record['after']['memory.events'][k] != record['before']['memory.events'][k]
               for k in ('oom', 'oom_kill')):
            record.update(complete=False, resource_error='OOM')
        if record['after']['cpu.stat']['nr_throttled'] != record['before']['cpu.stat']['nr_throttled']:
            record.update(complete=False, resource_error='CPU throttling')
        if engine:
            log = ''.join(engine.logs)
            if re.search(r'MISMATCH|TP check[^\n]*FAILED|illegal memory|nonfinite', log, re.IGNORECASE):
                record.update(complete=False, resource_error='Engine/checker error; inspect engine.log')
            if args.prune and args.diagnostic and not re.search(r'[1-9]\d* unpicked experts skipped', log):
                record.update(complete=False, resource_error='Pruning did not execute')
            record['known_blas_diagnostics'] = bool('rocblaslt error:' in log or 'hipModuleLoad failed:' in log)
        record['saved_results'] = len(rows)
        save(out / 'manifest.json', record)
        checkpoint(args.name + '-finished')
    raise SystemExit(0 if record['complete'] else 2)


if __name__ == '__main__':
    main()
