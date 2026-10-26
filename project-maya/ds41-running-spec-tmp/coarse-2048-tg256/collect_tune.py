#!/usr/bin/env python3
"""Locally collect only this sweep's allowlisted artifacts, fsync before ACK."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect import sync
from tune import SESSIONS

FILES = {'config.json', 'manifest.json', 'engine.log', 'protocol.log', 'results.jsonl'}
ROOT_FILES = {'experiment.json', 'point.json', 'summary.json', 'heartbeat.jsonl',
              *(f'stage-{i}.json' for i in range(1, 7))}


def destination(root, name):
    path = Path(name)
    if (path.is_absolute() or '..' in path.parts or
            not (name in ROOT_FILES or len(path.parts) == 2 and
                 path.parts[0] in SESSIONS and path.parts[1] in FILES)):
        raise ValueError(f'Unexpected artifact: {name}')
    return root / path


def store(root, record):
    if record['kind'] == 'artifact':
        path = destination(root, record['path'])
        path.parent.mkdir(exist_ok=True, parents=True)
        with path.open('a' if record['append'] else 'w') as f:
            f.write(record['data'])
            f.flush()
    elif record['kind'] not in ('checkpoint', 'progress'):
        raise ValueError('Unknown event')


def verified(root, code, count):
    path = root / 'summary.json'
    if code or not path.exists():
        return False
    state = json.loads(path.read_text())
    if not state['complete'] or count != state['saved_results'] or not state['sessions']:
        return False
    for session in state['sessions']:
        directory = root / session['name']
        manifest = json.loads((directory / 'manifest.json').read_text())
        rows = [json.loads(s) for s in (directory / 'results.jsonl').read_text().splitlines()]
        if not manifest['complete'] or not all(r['valid'] for r in rows):
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
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
    complete = verified(args.out, code, count)
    (args.out / 'exit.json').write_text(json.dumps({'returncode': code, 'saved_results': count,
                                                  'complete': complete}, indent=2) + '\n')
    sync(args.out)
    raise SystemExit(code if code else (0 if complete else 1))


if __name__ == '__main__':
    main()
