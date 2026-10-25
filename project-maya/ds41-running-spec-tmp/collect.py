#!/usr/bin/env python3
"""Persist screen stdout artifacts locally and ACK only after fsync."""
import argparse
import json
import os
from pathlib import Path
import subprocess

MODES = {'A-none', 'B-on-default', 'C-on-spread'}
FILES = {'config.json', 'manifest.json', 'engine.log', 'protocol.log', 'results.jsonl'}


def destination(root, name):
    path = Path(name)
    if (path.is_absolute() or '..' in path.parts or
            not (name in ('runs.json', 'heartbeat.jsonl') or
                 len(path.parts) == 2 and path.parts[0] in MODES and path.parts[1] in FILES)):
        raise ValueError(f'Unexpected artifact path: {name}')
    return root / path


def store(root, record):
    if record['kind'] == 'artifact':
        path = destination(root, record['path'])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a' if record['append'] else 'w') as f:
            f.write(record['data'])
            f.flush()
    elif record['kind'] not in ('checkpoint', 'progress'):
        raise ValueError(f'Unknown event: {record["kind"]}')


def sync(root):
    for path in root.rglob('*'):
        if path.is_file():
            with path.open('rb') as f:
                os.fsync(f.fileno())
    for path in [root, *(p for p in root.iterdir() if p.is_dir())]:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--modes', nargs='+', choices=sorted(MODES), default=sorted(MODES))
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('Command required')
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    count = 0
    with (args.out / 'events.jsonl').open('w') as events, (args.out / 'console.txt').open('w') as console:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1)
        try:
            for line in proc.stdout:
                if not line.startswith('SCREEN_EVENT '):
                    console.write(line)
                    console.flush()
                    continue
                record = json.loads(line.removeprefix('SCREEN_EVENT '))
                events.write(json.dumps(record, ensure_ascii=False) + '\n')
                events.flush()
                store(args.out, record)
                if record['kind'] == 'checkpoint':
                    sync(args.out)
                    proc.stdin.write('ACK ' + record['label'] + '\n')
                    proc.stdin.flush()
                    count += record['label'].endswith('-result')
                    print('SAVED ' + record['label'], flush=True)
                elif record['kind'] == 'progress':
                    print(record['value'], flush=True)
            code = proc.wait()
        finally:
            proc.stdout.close()
            proc.stdin.close()
            if proc.poll() is None:
                proc.terminate()
                proc.wait()
    expected = 6 * len(args.modes)
    complete = code == 0 and count == expected and all(
        (args.out / mode / 'manifest.json').exists() and
        json.loads((args.out / mode / 'manifest.json').read_text()).get('complete')
        for mode in args.modes)
    (args.out / 'exit.json').write_text(json.dumps({'returncode': code, 'saved_results': count,
                                                  'expected_results': expected, 'complete': complete}, indent=2) + '\n')
    sync(args.out)
    raise SystemExit(code if code else (0 if complete else 1))


if __name__ == '__main__':
    main()
