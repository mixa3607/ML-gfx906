#!/usr/bin/env python3
"""Three-start native DSpark screen; run inside the isolated Maya pod."""
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
import threading
import time
import traceback

from stream import artifact, checkpoint, progress, write_json

ROOT = Path('/data/screen')
MODES = [('A-none', 'none', None), ('B-on-default', 'on', None), ('C-on-spread', 'on', '1,2,3')]
MEMORY_GIB = int(os.environ.get('BENCH_MEMORY_GIB', '200'))
CURRENT = {'mode': None}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numbers(path):
    return {k: int(v) for k, v in (line.split() for line in path.read_text().splitlines())}


def snapshot(pid=None):
    cg = Path('/sys/fs/cgroup')
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::'):
            nested = cg / line[3:].lstrip('/')
            if (nested / 'memory.current').is_file():
                cg = nested
    out = {name: (cg / name).read_text().strip() for name in
           ('memory.current', 'memory.peak', 'memory.max', 'cpu.max', 'cpuset.cpus.effective')}
    out.update({name: numbers(cg / name) for name in ('memory.stat', 'memory.events', 'cpu.stat')})
    if pid:
        out['process_io'] = numbers(Path(f'/proc/{pid}/io'))
        out['process_status'] = Path(f'/proc/{pid}/status').read_text()
    out['unix'] = time.time()
    return out


def parse_done(line):
    parts = line.split()
    if len(parts) != 11 or parts[0] != 'DONE':
        raise ValueError(f'Unexpected DONE: {line}')
    return dict(tg=int(parts[1]), pp=int(parts[2]), prompt_ms=float(parts[3]),
                decode_ms=float(parts[4]), finish=parts[5], accepted=int(parts[6]),
                drafted=int(parts[7]), reused=int(parts[8]), hits=int(parts[9]), lookups=int(parts[10]))


def validate(row, spec):
    done = row['done']
    if done['pp'] != 2048 or done['reused'] != 0:
        raise ValueError(f'Incomplete prefill or cross-request reuse: {done}')
    if done['tg'] != len(row['tokens']) or done['tg'] > 256:
        raise ValueError(f'Inconsistent TG: {done}')
    if done['tg'] != 256 or done['finish'] != 'length':
        raise ValueError(f'Natural EOS or incomplete request, not a TG256 sample: {done}')
    if not spec and (done['drafted'] or done['accepted']):
        raise ValueError('Baseline unexpectedly speculated')
    if not 0 <= done['accepted'] <= done['drafted']:
        raise ValueError('Invalid draft counters')
    if any(not math.isfinite(done[k]) or done[k] <= 0 for k in ('prompt_ms', 'decode_ms')):
        raise ValueError('Invalid native timings')
    if any(float(s.get('skipped', 0)) for s in row['stats']):
        raise ValueError('Approximate expert skipping occurred')
    before, after = row['before'], row['after']
    if after['memory.events']['oom_kill'] != before['memory.events']['oom_kill']:
        raise ValueError('OOM during request')
    if after['cpu.stat']['nr_throttled'] != before['cpu.stat']['nr_throttled']:
        raise ValueError('CPU throttling during request')


class Engine:
    def __init__(self, config, out):
        self.out = out
        self.log = (out / 'engine.log').open('w')
        self.protocol = (out / 'protocol.log').open('w')
        self.copies_logged = threading.Event()
        self.proc = subprocess.Popen([config['exe'], *config['args'], '--serve'], cwd=config['cwd'],
                                     env=config['env'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, start_new_session=True)
        self.log_thread = threading.Thread(target=self.capture_log, daemon=True)
        self.log_thread.start()
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.buffer = b''

    def capture_log(self):
        for raw in self.proc.stderr:
            text = raw.decode('utf-8', errors='replace')
            self.log.write(text)
            self.log.flush()
            artifact(self.out / 'engine.log', text, append=True)
            if 'experts copied into RAM' in text:
                self.copies_logged.set()

    def line(self, deadline):
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not self.selector.select(remaining):
                raise TimeoutError('Native engine deadline exceeded')
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError(f'Native engine exited: {self.proc.poll()}')
            self.buffer += chunk
            artifact(self.out / 'protocol.log', chunk.decode('utf-8', errors='replace'), append=True)
        raw, self.buffer = self.buffer.split(b'\n', 1)
        line = raw.decode('utf-8', errors='replace')
        self.protocol.write(line + '\n')
        self.protocol.flush()
        return line

    def ready(self):
        deadline = time.monotonic() + 1800
        lines = []
        while True:
            line = self.line(deadline)
            lines.append(line)
            if line.startswith('ERR '):
                raise RuntimeError(line)
            if line.startswith('READY '):
                return lines

    def request(self, case, spec):
        before = snapshot(self.proc.pid)
        start = time.monotonic()
        message = f'GEN 256 temperature=0 seed=1 spec={int(spec)} ' + ','.join(map(str, case['ids'])) + '\n'
        self.proc.stdin.write(message.encode())
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
               'done': done, 'wall_s': elapsed, 'ttft_s': times[0] if times else None,
               'token_delivery_s': times, 'tokens': tokens, 'stats': stats,
               'before': before, 'after': snapshot(self.proc.pid)}
        row['pp_tok_s'] = 1000 * done['pp'] / done['prompt_ms'] if done['prompt_ms'] else None
        row['native_tg_tok_s'] = 1000 * (done['tg'] - 1) / done['decode_ms'] if done['decode_ms'] else None
        row['delivery_tg_tok_s'] = ((len(tokens) - 1) / (times[-1] - times[0])
                                    if len(tokens) > 1 and times[-1] > times[0] else None)
        try:
            validate(row, spec)
            row['valid'] = True
        except ValueError as error:
            row.update(valid=False, error=str(error))
        return row

    def close(self):
        try:
            if self.proc.poll() is None:
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
        finally:
            self.selector.close()
            self.proc.stdin.close()
            self.proc.stdout.close()
            self.log_thread.join(timeout=15)
            self.proc.stderr.close()
            self.log.close()
            self.protocol.close()


def run_mode(base, cases, name, mode, placement):
    CURRENT['mode'] = name
    out = ROOT / name
    out.mkdir(exist_ok=False)
    profile = out / 'expert-profile.bin'
    shutil.copyfile(ROOT / 'seed-profile.bin', profile)
    args = list(base['args'])
    args[args.index('--dspark') + 1] = mode
    args[args.index('--expert-profile') + 1] = str(profile)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DS4_', 'STRATA_DS4_', 'MAYA_DS4_'))}
    env.update(base['env'])
    if placement:
        env['DS4_DRAFT_DEV'] = placement
    # Save only explicit runtime overrides, never the inherited process environment.
    config = {'exe': base['exe'], 'cwd': base['cwd'], 'args': args,
              'env': base['env'] | ({'DS4_DRAFT_DEV': placement} if placement else {})}
    write_json(out / 'config.json', config)
    config['env'] = env
    record = {'name': name, 'mode': mode, 'placement': placement, 'before': snapshot(),
              'seed_profile_sha256': sha(profile), 'cases_sha256': sha(ROOT / 'cases.jsonl'),
              'source_commit': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
              'build': json.loads(Path('/opt/maya/build-hip/MAYA-BUILD.json').read_text()),
              'runner_sha256': sha(Path(__file__)), 'complete': False, 'stage': 'starting',
              'memory_gib': MEMORY_GIB}
    write_json(out / 'manifest.json', record)
    checkpoint(name + '-starting')
    engine = None
    progress(f'START {name}')
    try:
        if MEMORY_GIB not in (200, 220) or record['before']['memory.max'] != str(MEMORY_GIB * 2**30) or not record['before']['cpu.max'].startswith('max '):
            raise ValueError(f'Expected {MEMORY_GIB}Gi memory cap and no CPU quota')
        started = time.monotonic()
        engine = Engine(config, out)
        record['ready'] = engine.ready()
        record['load_s'] = time.monotonic() - started
        engine.copies_logged.wait(timeout=5)
        log = (out / 'engine.log').read_text()
        copies = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM", log)
        record['full_copies'] = list(map(int, copies.groups())) if copies else None
        if not copies or copies[1] != copies[2]:
            raise ValueError('Not all CPU-lane experts copied into RAM')
        vram = [dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)
                for line in record['ready'] if line.startswith('VRAM ')]
        if (len(vram) != 4 or any(v.get('tp_n') != '4' or v.get('ctx') != '196608' for v in vram)
                or not any('vision=ds4 ' in line for line in record['ready'])):
            raise ValueError('TP4/context196608/native vision not verified')
        record['ready_snapshot'] = snapshot(engine.proc.pid)
        record['stage'] = 'ready'
        write_json(out / 'manifest.json', record)
        checkpoint(name + '-ready')
        progress(f'READY {name} {record["load_s"]:.1f}s copies={record["full_copies"]}')
        with (out / 'results.jsonl').open('x') as results:
            for case in cases:
                row = engine.request(case, mode == 'on')
                text = json.dumps(row, ensure_ascii=False) + '\n'
                results.write(text)
                results.flush()
                artifact(out / 'results.jsonl', text, append=True)
                checkpoint(name + '-' + case['id'] + '-result')
                progress({'name': name, **{k: row[k] for k in
                          ('id', 'done', 'wall_s', 'pp_tok_s', 'native_tg_tok_s', 'valid')}})
                if not row['valid']:
                    raise ValueError(row['error'])
        record['complete'] = True
        record['stage'] = 'complete'
    except Exception:
        record['error'] = traceback.format_exc()
        record['stage'] = 'error'
        progress(record['error'])
    finally:
        if engine:
            engine.close()
        record['after'] = snapshot()
        write_json(out / 'manifest.json', record)
        checkpoint(name + '-finished')
    return record


def main():
    base = json.loads((ROOT / 'baseline.json').read_text())
    cases = [json.loads(line) for line in (ROOT / 'cases.jsonl').read_text().splitlines()]
    if [c['phase'] for c in cases] != ['warmup'] * 3 + ['measurement'] * 3:
        raise ValueError('Expected three warmup followed by three measurement cases')
    if any(len(c['ids']) != 2048 for c in cases):
        raise ValueError('Expected PP2048')
    stop = threading.Event()

    def heartbeat():
        with (ROOT / 'heartbeat.jsonl').open('x') as f:
            while not stop.wait(15):
                text = json.dumps({'mode': CURRENT['mode'], 'snapshot': snapshot()}) + '\n'
                f.write(text)
                f.flush()
                artifact(ROOT / 'heartbeat.jsonl', text, append=True)

    monitor = threading.Thread(target=heartbeat, daemon=True)
    monitor.start()
    records = []
    try:
        for name, mode, placement in MODES:
            record = run_mode(base, cases, name, mode, placement)
            records.append(record)
            if not record['complete'] and name == 'A-none':
                break
    finally:
        stop.set()
        monitor.join(timeout=5)
    write_json(ROOT / 'runs.json', records)
    checkpoint('screen-finished')
    progress('SCREEN FINISHED')


if __name__ == '__main__':
    main()
