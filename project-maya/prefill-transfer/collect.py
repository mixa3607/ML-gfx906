#!/usr/bin/env python3
"""Persist each remote evidence checkpoint before acknowledging execution."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def destination(root, name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts or len(path.parts) != 2:
        raise ValueError('Unsafe artifact path')
    if path.name not in ('config.json', 'manifest.json', 'engine.log', 'protocol.log', 'results.jsonl'):
        raise ValueError('Unexpected artifact')
    return root / path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    args.out.mkdir(parents=True, exist_ok=False)
    count = 0
    with (args.out / 'events.jsonl').open('w') as events, (args.out / 'console.txt').open('w') as console:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1)
        try:
            for line in proc.stdout:
                if not line.startswith('BENCH_EVENT '):
                    console.write(line)
                    console.flush()
                    continue
                event = json.loads(line.removeprefix('BENCH_EVENT '))
                events.write(json.dumps(event) + '\n')
                events.flush()
                if event['kind'] == 'artifact':
                    path = destination(args.out, event['path'])
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('a' if event['append'] else 'w') as f:
                        f.write(event['data'])
                        f.flush()
                elif event['kind'] == 'checkpoint':
                    for path in args.out.rglob('*'):
                        if path.is_file():
                            with path.open('rb') as f:
                                os.fsync(f.fileno())
                    proc.stdin.write('ACK ' + event['label'] + '\n')
                    proc.stdin.flush()
                    count += event['label'].endswith('-result')
                    print('SAVED ' + event['label'], flush=True)
                elif event['kind'] == 'progress':
                    value = event['value']
                    # Heartbeat details remain durable but do not flood the console.
                    if not isinstance(value, dict) or 'memory' not in value:
                        print(value, flush=True)
                else:
                    raise ValueError('Unknown event kind')
            code = proc.wait()
        finally:
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=30)
    manifests = list(args.out.glob('*/manifest.json'))
    manifest = json.loads(manifests[0].read_text()) if len(manifests) == 1 else {}
    complete = bool(code == 0 and manifest.get('complete') and count == manifest.get('saved_results'))
    (args.out / 'exit.json').write_text(json.dumps({'returncode': code, 'saved_results': count,
                                                  'complete': complete}, indent=2) + '\n')
    raise SystemExit(0 if complete else code or 1)


if __name__ == '__main__':
    main()
