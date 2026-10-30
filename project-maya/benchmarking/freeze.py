#!/usr/bin/env python3
"""Command line for the shared benchmark kit.

    freeze.py fetch  SUITE_DIR [--out FILE] [--resume]
    freeze.py freeze SUITE_DIR [--source FILE] [--out-dir DIR] [--tokenizer DIR]
                                [--maya-root DIR] [--force]

``SUITE_DIR`` is a directory such as ``CORPUS-DS41F/`` with a ``suite.py`` that
defines ``SUITE``, ``SOURCES``, ``TASKS`` and ``TASK_LABELS``.  The suite decides
what is measured (model, article pools, tasks, seed, PP schedule, TG); this
command and ``benchkit.py`` decide how it is cut, checked and frozen.

The tokenizer and chat encoder come from a Maya source checkout, so run this in
a Maya image (its environment provides ``regex`` and ``jinja2``):

    MAYA_ROOT=/src python3 freeze.py freeze CORPUS-DS41F \
        --tokenizer /data/ds4/tokenizer

See ``README.md`` for the full container command.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

import benchkit


def load_suite(directory):
    path = Path(directory) / 'suite.py'
    if not path.is_file():
        raise SystemExit(f'{path} not found; SUITE_DIR must contain suite.py')
    spec = importlib.util.spec_from_file_location('suite', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name in ('SUITE', 'SOURCES', 'TASKS', 'TASK_LABELS'):
        if not hasattr(module, name):
            raise SystemExit(f'{path} does not define {name}')
    return module


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    fetch = sub.add_parser('fetch', help='download the articles listed in the suite SOURCES')
    fetch.add_argument('suite_dir', type=Path)
    fetch.add_argument('--out', type=Path, help='default: SUITE_DIR/sources.jsonl')
    fetch.add_argument('--resume', action='store_true')

    freeze = sub.add_parser('freeze', help='cut and freeze the suite')
    freeze.add_argument('suite_dir', type=Path)
    freeze.add_argument('--source', type=Path, help='default: SUITE_DIR/sources.jsonl')
    freeze.add_argument('--out-dir', type=Path, help='default: SUITE_DIR')
    freeze.add_argument('--tokenizer', default='/data/ds4/tokenizer')
    freeze.add_argument('--maya-root', default=os.environ.get('MAYA_ROOT', '/opt/maya'))
    freeze.add_argument('--force', action='store_true')

    args = ap.parse_args()
    suite_dir = args.suite_dir.resolve()
    suite = load_suite(suite_dir)

    if args.command == 'fetch':
        out = args.out or suite_dir / 'sources.jsonl'
        benchkit.fetch_articles(suite.SOURCES, out, args.resume)
        return 0

    source = (args.source or suite_dir / 'sources.jsonl').resolve()
    out = (args.out_dir or suite_dir).resolve()
    if not source.is_file():
        raise SystemExit(f'{source} not found; run "fetch" first or point --source at frozen sources')
    manifest = benchkit.freeze_suite(suite.SUITE, suite.TASKS, suite.TASK_LABELS, out, source,
                                     args.tokenizer, args.maya_root, args.force)
    print(json.dumps({'suite': manifest['suite'], 'cases': len(manifest['order']),
                      'tg': manifest['tg'], 'files': manifest['files']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
