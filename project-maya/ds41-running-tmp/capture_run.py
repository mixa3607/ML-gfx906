#!/usr/bin/env python3
"""Run kubectl exec (or a test command), saving streamed records outside the pod."""
import argparse
import json
import os
from pathlib import Path
import subprocess


FILES = {'manifest': 'manifest.json', 'ready': 'ready.json', 'after': 'after.json',
         'verdict': 'verdict.json', 'vision_manifest': 'vision/manifest.json',
         'vision_ready': 'vision/ready.json'}


def durable_write(path, value, append=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a' if append else 'w') as f:
        f.write(json.dumps(value, ensure_ascii=False) + '\n')
        f.flush()
        os.fsync(f.fileno())


def store_event(root, record):
    kind, value = record['kind'], record['value']
    if kind in FILES:
        durable_write(root / FILES[kind], value)
    elif kind == 'result':
        durable_write(root / 'results.jsonl', value, append=True)
    elif kind == 'vision_result' and value['case'] in ('shapes', 'blank'):
        durable_write(root / 'vision' / f'{value["case"]}.json', value)
    else:
        raise ValueError(f'Unknown streamed event: {kind}')
    durable_write(root / 'events.jsonl', record, append=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--expected-results', type=int, required=True)
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    command = a.command[1:] if a.command[:1] == ['--'] else a.command
    if not command or a.expected_results < 1:
        p.error('A command and positive expected result count are required')
    a.out.mkdir(parents=True, exist_ok=False)
    durable_write(a.out / 'command.json', command)
    count = 0
    with (a.out / 'console.log').open('w') as console:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', bufsize=1)
        try:
            for line in proc.stdout:
                if line.startswith('BENCH_EVENT '):
                    record = json.loads(line.removeprefix('BENCH_EVENT '))
                    store_event(a.out, record)
                    count += record['kind'] == 'result'
                else:
                    console.write(line)
                    console.flush()
                    os.fsync(console.fileno())
                    print(line, end='', flush=True)
            code = proc.wait()
        finally:
            proc.stdout.close()
            if proc.poll() is None:
                proc.terminate()
                proc.wait()
    complete = code == 0 and count == a.expected_results
    durable_write(a.out / 'exit.json', {'returncode': code, 'results': count,
                                       'expected_results': a.expected_results, 'complete': complete})
    if not complete:
        raise SystemExit(code if code > 0 else 1)


if __name__ == '__main__':
    main()
