#!/usr/bin/env python3
"""Persist the bounded code/Russian suite outside the pod and ACK after fsync."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect import sync
from bench import SESSIONS

NAMES = {s[0] for s in SESSIONS}
FILES = {'manifest.json', 'config.json', 'engine.log', 'protocol.log', 'results.jsonl'}


def destination(root, name):
    path = Path(name)
    if (path.is_absolute() or '..' in path.parts or not (
            name in ('experiment.json', 'summary.json', 'heartbeat.jsonl') or
            len(path.parts) == 2 and path.parts[0] in NAMES and path.parts[1] in FILES)):
        raise ValueError('Unexpected artifact path: ' + name)
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
    summary_path = args.out / 'summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    complete = code == 0 and count == 66 and summary.get('complete') and summary.get('saved_results') == count
    (args.out / 'exit.json').write_text(json.dumps({'returncode': code, 'saved_results': count,
                                                  'expected_results': 66, 'complete': bool(complete)}, indent=2) + '\n')
    sync(args.out)
    raise SystemExit(code if code else (0 if complete else 1))


if __name__ == '__main__':
    main()
