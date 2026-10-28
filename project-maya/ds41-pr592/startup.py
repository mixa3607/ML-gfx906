#!/usr/bin/env python3
"""Unscored TP2 load and native generation gate; stop the engine on all exits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import time
import traceback


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def snapshot():
    root = Path('/sys/fs/cgroup')
    for line in Path('/proc/self/cgroup').read_text().splitlines():
        if line.startswith('0::'):
            nested = root / line[3:].lstrip('/')
            if (nested / 'memory.current').is_file():
                root = nested
    result = {}
    for name in ('memory.current', 'memory.peak', 'memory.max', 'memory.events', 'cpu.max', 'cpu.stat'):
        result[name] = (root / name).read_text().strip()
    return result


class Engine:
    def __init__(self, config, output):
        self.log = (output / 'engine.log').open('w')
        self.protocol = (output / 'protocol.log').open('w')
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(('DS4_', 'STRATA_', 'MAYA_', 'HSA_OVERRIDE_'))}
        env.update(config['env'])
        self.proc = subprocess.Popen([config['exe'], *config['args'], '--serve'],
                                     cwd=config['cwd'], env=env, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=self.log, start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)
        self.buffer = b''

    def line(self, deadline):
        while b'\n' not in self.buffer:
            if not self.selector.select(max(0, deadline - time.monotonic())):
                raise TimeoutError('Engine deadline exceeded')
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError(f'Engine exited: {self.proc.poll()}')
            self.buffer += chunk
        raw, self.buffer = self.buffer.split(b'\n', 1)
        line = raw.decode('utf-8', errors='replace')
        self.protocol.write(line + '\n')
        self.protocol.flush()
        if line.startswith('ERR '):
            raise RuntimeError(line)
        return line

    def ready(self):
        lines = []
        deadline = time.monotonic() + 1800
        while True:
            line = self.line(deadline)
            lines.append(line)
            print(line, flush=True)
            if line.startswith('READY '):
                return lines

    def close(self):
        try:
            if self.proc.poll() is None:
                self.proc.stdin.write(b'STOP\nQUIT\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=60)
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
            self.protocol.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--peer', action='store_true')
    ap.add_argument('--name', default='startup')
    args = ap.parse_args()
    source = Path(__file__).resolve().parent
    out = Path('/data') / args.name
    out.mkdir(exist_ok=True)
    config = json.loads((source / 'runtime.json').read_text())
    if args.peer:
        config['env']['DS4_HIP_PEER_AR'] = '1'
    shutil.copyfile('/data/seed-profile.bin', out / 'expert-profile.bin')
    config['args'][config['args'].index('--expert-profile') + 1] = str(out / 'expert-profile.bin')
    write_json(out / 'config.json', config)
    record = {'complete': False, 'before': snapshot(),
              'source_commit': Path('/opt/maya/SOURCE_COMMIT').read_text().strip(),
              'build': json.loads(Path('/opt/maya/build-hip/MAYA-BUILD.json').read_text()),
              'seed_profile_sha256': hashlib.sha256(Path('/data/seed-profile.bin').read_bytes()).hexdigest()}
    engine = None
    try:
        started = time.monotonic()
        engine = Engine(config, out)
        record['ready'] = engine.ready()
        record['load_s'] = time.monotonic() - started
        vram = [dict(p.split('=', 1) for p in line.split()[1:] if '=' in p)
                for line in record['ready'] if line.startswith('VRAM ')]
        if len(vram) != 4 or any(v.get('tp_n') != '2' or v.get('ctx') != '196608' for v in vram):
            raise ValueError('Four GPUs / TP2 / context196608 not confirmed')
        record['peer_groups_enabled'] = (out / 'engine.log').read_text().count('exact peer prefill all-reduce enabled')
        if args.peer and record['peer_groups_enabled'] != 2:
            raise ValueError('Peer transport did not activate on both TP2 groups')
        case = json.loads((source / 'startup-case.json').read_text())
        write_json(out / 'input.json', case)
        started = time.monotonic()
        engine.proc.stdin.write(('GEN 32 temperature=0 seed=1 spec=1 dspark_conf=0.5 dspark_cum=0.5 '
                                 + ','.join(map(str, case['ids'])) + '\n').encode())
        engine.proc.stdin.flush()
        tokens = []
        while True:
            line = engine.line(started + 900)
            print(line, flush=True)
            if line.startswith('T '):
                tokens.append(int(line.split()[1]))
            elif line.startswith('DONE '):
                record['done'] = line
                break
        parts = record['done'].split()
        if int(parts[1]) != len(tokens) or not tokens or int(parts[2]) != len(case['ids']) or int(parts[8]):
            raise ValueError('Invalid generation or cross-request reuse')
        import sys
        sys.path.insert(0, '/opt/maya/tools')
        from strata_tokenizer import Tokenizer
        tok = Tokenizer.from_dir('/data/ds4/tokenizer')
        record.update(complete=True, tokens=tokens, request_wall_s=time.monotonic() - started,
                      output_text=b''.join(tok.token_bytes(t) for t in tokens).decode('utf-8', errors='replace'))
    except Exception:
        record['error'] = traceback.format_exc()
    finally:
        if engine:
            engine.close()
            record['engine_exit_code'] = engine.proc.returncode
        record['after'] = snapshot()
        write_json(out / 'result.json', record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
    return 0 if record['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
