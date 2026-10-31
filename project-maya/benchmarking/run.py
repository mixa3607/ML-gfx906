#!/usr/bin/env python3
"""Run frozen requests through one resident Maya engine."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def read_until(stream, prefix):
    while True:
        line = next(stream).rstrip()
        if line.startswith('ERR '):
            raise RuntimeError(line)
        if line.startswith(prefix):
            return line


def parse_done(line):
    (
        _, generated, prompt_tokens, prompt_ms, decode_ms, finish,
        drafts_accepted, drafts_offered, reused, hits, lookups,
    ) = line.split()
    return {
        'generated': int(generated),
        'prompt_tokens': int(prompt_tokens),
        'prompt_ms': float(prompt_ms),
        'decode_ms': float(decode_ms),
        'finish': finish,
        'drafts_accepted': int(drafts_accepted),
        'drafts_offered': int(drafts_offered),
        'reused': int(reused),
        'hits': int(hits),
        'lookups': int(lookups),
    }


def run(cases, engine):
    read_until(engine.stdout, 'READY ')
    for line in cases:
        case = json.loads(line)
        ids = ','.join(map(str, case['ids']))
        engine.stdin.write(f"GEN {case['tg']} temperature=0 spec=0 {ids}\n")
        engine.stdin.flush()
        done = parse_done(read_until(engine.stdout, 'DONE '))
        print(json.dumps({'id': case['id'], 'phase': case['phase'], 'done': done}), flush=True)
    engine.stdin.write('QUIT\n')
    engine.stdin.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cases', type=Path)
    parser.add_argument('--maya-root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()

    maya_root = args.maya_root.resolve()
    sys.path.insert(0, str(maya_root))
    # Import the launch settings from the external Maya checkout.
    from serve.server import child_env, engine_args  # pyright: ignore[reportMissingImports]

    cfg = json.loads(args.config.read_text())
    with args.cases.open() as cases, subprocess.Popen(
        [cfg['exe'], '--serve', *engine_args(cfg)],
        cwd=cfg.get('cwd') or maya_root,
        env=child_env(cfg),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as engine:
        run(cases, engine)


if __name__ == '__main__':
    main()
