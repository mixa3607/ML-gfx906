#!/usr/bin/env python3
"""Serial DS4 engine benchmark. Run inside the Maya image; no HTTP timing claims."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import struct
import subprocess
import time

from full_compute import POLICY, engine_env, validate_config, validate_limits


def read_numbers(path):
    try:
        return {k: int(v) for k, v in (line.split() for line in path.read_text().splitlines())}
    except (OSError, ValueError):
        return {}


def cgroup_dir():
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::'):
            return Path('/sys/fs/cgroup') / line[3:].lstrip('/')
    raise RuntimeError('cgroup v2 is required for memory and CPU accounting')


def snapshot(pid=None):
    cg = cgroup_dir()
    out = {'cpu': read_numbers(cg / 'cpu.stat'),
           'memory_stat': read_numbers(cg / 'memory.stat'),
           'memory_events': read_numbers(cg / 'memory.events')}
    for name in ('cpu.max', 'memory.max', 'memory.current', 'memory.peak', 'cpuset.cpus.effective'):
        p = cg / name
        if p.exists():
            out[name] = p.read_text().strip()
    if pid:
        out['io'] = read_numbers(Path(f'/proc/{pid}/io'))
        out['status'] = Path(f'/proc/{pid}/status').read_text()
    return out


def quantile(values, q):
    if not values:
        return None
    values = sorted(values)
    return values[round((len(values) - 1) * q)]


def parse_done(line):
    p = line.split()
    if len(p) != 11 or p[0] != 'DONE':
        raise ValueError(f'Unexpected DS4 DONE format: {line}')
    return dict(tg=int(p[1]), pp=int(p[2]), prompt_ms=float(p[3]),
                decode_ms=float(p[4]), finish=p[5], accepted=int(p[6]),
                drafted=int(p[7]), reused=int(p[8]), hits=int(p[9]), lookups=int(p[10]))


def dump_hashes(path, vocab=129280):
    row_bytes = vocab * 4
    whole = hashlib.sha256()
    rows = []
    with path.open('rb') as f:
        while row := f.read(row_bytes):
            if len(row) != row_bytes:
                raise RuntimeError(f'Incomplete logits row in {path}')
            if not all(map(math.isfinite, memoryview(row).cast('f'))):
                raise RuntimeError(f'Non-finite logits in {path}, row {len(rows)}')
            whole.update(row)
            rows.append(hashlib.sha256(row).hexdigest())
    if not rows:
        raise RuntimeError('No logits were dumped')
    return {'sha256': whole.hexdigest(), 'rows': rows, 'vocab': vocab, 'finite': True}


class Engine:
    def __init__(self, cfg, output, dump=False):
        self.output = output
        self.log = (output / 'engine.log').open('w')
        self.transcript = (output / 'protocol.log').open('w')
        self.profile = output / 'expert-profile.bin'
        shutil.copyfile(cfg['seed_profile'], self.profile)
        env = (engine_env(cfg, os.environ) if cfg.get('policy') == POLICY
               else {**os.environ, **cfg['env']})
        env['DS4_LANE_CAL'] = str(output / 'lane-times.txt')
        env.pop('DS4_SERVE_DUMP', None)
        if dump:
            env['DS4_SERVE_DUMP'] = str(output / 'logits')
        self.cmd = [cfg['exe'], *cfg['args'], '--expert-profile', str(self.profile), '--serve']
        affinity = cfg.get('cpu_affinity')
        if affinity is not None:
            allowed = os.sched_getaffinity(0)
            if not affinity or not set(affinity) <= allowed:
                raise ValueError('Requested CPU affinity is outside the available cpuset')
            os.sched_setaffinity(0, affinity)
        try:
            self.proc = subprocess.Popen(self.cmd, cwd=cfg['cwd'], env=env,
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=self.log, start_new_session=True)
        finally:
            if affinity is not None:
                os.sched_setaffinity(0, allowed)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.buffer = b''
        self.count = 0

    def line(self, deadline):
        while b'\n' not in self.buffer:
            if not self.selector.select(max(0, deadline - time.monotonic())):
                raise TimeoutError('Engine deadline exceeded; see engine.log')
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError(f'Engine exited ({self.proc.poll()}); see engine.log')
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b'\n', 1)
        text = line.decode('utf-8', errors='replace')
        self.transcript.write(text + '\n')
        self.transcript.flush()
        return text

    def ready(self, timeout):
        deadline = time.monotonic() + timeout
        lines = []
        while True:
            line = self.line(deadline)
            lines.append(line)
            if line.startswith('READY '):
                return lines
            if line.startswith('ERR '):
                raise RuntimeError(line)

    def request(self, case, timeout, tg, benchmark=True):
        self.count += 1
        before = snapshot(self.proc.pid)
        started = time.monotonic()
        times, tokens, stats = [], [], []
        request = f'GEN {tg} temperature=0 seed=1 spec=0 ' + ','.join(map(str, case['ids'])) + '\n'
        self.proc.stdin.write(request.encode())
        self.proc.stdin.flush()
        deadline = started + timeout
        while True:
            line = self.line(deadline)
            at = time.monotonic()
            if line.startswith('T '):
                tokens.append(int(line.split()[1]))
                times.append(at)
            elif line.startswith('STAT '):
                stats.append(dict(part.split('=', 1) for part in line.split()[1:]))
            elif line.startswith('ERR '):
                raise RuntimeError(line)
            elif line.startswith('DONE '):
                done = parse_done(line)
                break
        elapsed = time.monotonic() - started
        after = snapshot(self.proc.pid)
        if done['reused'] or done['drafted'] or done['accepted']:
            raise RuntimeError(f'Invalid benchmark: KV reuse or speculation: {done}')
        if not tokens or done['tg'] != len(tokens) or len(tokens) > tg or done['pp'] != len(case['ids']):
            raise RuntimeError(f'Not PP{len(case["ids"])} / TG{tg}: {done}')
        if benchmark and (done['tg'] != tg or done['finish'] != 'length'):
            raise RuntimeError(f'Request did not reach TG limit: {done}')
        if done['finish'] not in ('length', 'stop'):
            raise RuntimeError(f'Unexpected finish reason: {done}')
        if any(not math.isfinite(done[k]) or done[k] <= 0 for k in ('prompt_ms', 'decode_ms')):
            raise RuntimeError(f'Non-finite or nonpositive engine timing: {done}')
        if any(float(s.get('skipped', 0)) for s in stats):
            raise RuntimeError('An expert was skipped')
        if after['memory_events'].get('oom_kill', 0) > before['memory_events'].get('oom_kill', 0):
            raise RuntimeError('cgroup OOM kill during request')
        if after['cpu'].get('nr_throttled', 0) > before['cpu'].get('nr_throttled', 0):
            raise RuntimeError('CPU throttling during request')
        intervals = [b - a for a, b in zip(times, times[1:])]
        return {k: v for k, v in case.items() if k != 'ids'} | {
            'done': done, 'wall_s': elapsed, 'ttft_s': times[0] - started,
            'pp_tok_s': 1000 * done['pp'] / done['prompt_ms'],
            'tg_tok_s': (len(tokens) - 1) / (times[-1] - times[0]) if len(tokens) > 1 else None,
            'itl_p50_s': quantile(intervals, .5), 'itl_p95_s': quantile(intervals, .95),
            'itl_p99_s': quantile(intervals, .99), 'tokens': tokens, 'stats': stats,
            'before': before, 'after': after,
            'token_sha256': hashlib.sha256(struct.pack(f'<{len(tokens)}i', *tokens)).hexdigest()}

    def close(self):
        try:
            if self.proc.poll() is None:
                # STOP is consumed by the input thread; QUIT shuts down after the current request.
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
            self.log.close()
            self.transcript.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', type=Path, required=True)
    ap.add_argument('--cases', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--timeout', type=int, default=7200)
    ap.add_argument('--tg', type=int, choices=[256], default=256)
    ap.add_argument('--dump', action='store_true', help='Validation only: hash every f32 logits row')
    a = ap.parse_args()
    cfg = json.loads(a.config.read_text())
    policy = None
    if 'policy' in cfg:
        policy = validate_config(cfg)
        validate_limits(snapshot())
    cases = [json.loads(s) for s in a.cases.read_text().splitlines() if s.strip()]
    if not cases or any(not c['ids'] or len(c['ids']) % 2048 or len(c['ids']) + a.tg > 196608 for c in cases):
        raise ValueError('Cases must use PP multiples of 2048 and fit context 196608')
    a.out.mkdir(parents=True, exist_ok=False)
    (a.out / 'config.json').write_text(json.dumps(cfg, indent=2) + '\n')
    (a.out / 'manifest.json').write_text(json.dumps({
        'cases_sha256': hashlib.sha256(a.cases.read_bytes()).hexdigest(),
        'config_sha256': hashlib.sha256(a.config.read_bytes()).hexdigest(),
        'seed_profile_sha256': hashlib.sha256(Path(cfg['seed_profile']).read_bytes()).hexdigest(),
        'build': json.loads(Path('/opt/maya/build-hip/MAYA-BUILD.json').read_text()),
        'source_commit': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'dump': a.dump, 'tg': a.tg, 'cgroup': str(cgroup_dir()), 'policy': policy,
        'policy_sha256': hashlib.sha256(Path(__file__).with_name('full_compute.py').read_bytes()).hexdigest(),
        'before': snapshot(), 'started_unix': time.time()}, indent=2) + '\n')
    engine = Engine(cfg, a.out, a.dump)
    try:
        t0 = time.monotonic()
        ready = engine.ready(a.timeout)
        if policy and (not any(line.startswith('READY 196608 ') for line in ready)
                       or not any(line.startswith('INFO ') and 'vision=ds4 ' in line for line in ready)):
            raise RuntimeError('Context196608 or native DS4 vision not available')
        if cfg.get('require_full_copies'):
            log = (a.out / 'engine.log').read_text()
            match = re.search(r"(\d+) of the CPU lane's (\d+) experts copied into RAM", log)
            if not match or match[1] != match[2]:
                raise RuntimeError('Full-copy candidate did not copy every CPU expert; see engine.log')
        (a.out / 'ready.json').write_text(json.dumps({
            'load_s': time.monotonic() - t0, 'lines': ready, 'snapshot': snapshot(engine.proc.pid)}, indent=2) + '\n')
        print(f'READY {cfg["name"]}: {time.monotonic() - t0:.1f}s', flush=True)
        with (a.out / 'results.jsonl').open('w') as out:
            for case in cases:
                print(f'START {case["id"]} PP{len(case["ids"])} TG{a.tg}', flush=True)
                row = engine.request(case, a.timeout, a.tg)
                if a.dump:
                    p = a.out / f'logits.{engine.count}.f32'
                    row['logits'] = dump_hashes(p)
                    if len(row['logits']['rows']) != a.tg:
                        raise RuntimeError('Expected one logits row per output token')
                    p.unlink()
                out.write(json.dumps(row, ensure_ascii=False) + '\n')
                out.flush()
                print(f'{case["id"]}: pp={row["pp_tok_s"]:.2f} tg={row["tg_tok_s"]:.2f} '
                      f'ttft={row["ttft_s"]:.2f}s disk={row["stats"][-1].get("disk_mb")} MB/t', flush=True)
    finally:
        engine.close()
        (a.out / 'after.json').write_text(json.dumps(snapshot(), indent=2) + '\n')


if __name__ == '__main__':
    main()
