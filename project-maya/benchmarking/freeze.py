#!/usr/bin/env python3
"""Command line for the shared benchmark kit.

    freeze.py fetch   CORPUS_DIR [--out FILE] [--resume]
    freeze.py sources CORPUS_DIR [--source FILE] [--force]
    freeze.py freeze  SUITE_DIR  [--source FILE] [--out-dir DIR] [--tokenizer DIR]
                                 [--maya-root DIR] [--force]

``CORPUS_DIR`` is a directory such as ``corpora/ru-prose/`` with a ``corpus.py``
that defines the article pools and tasks.  ``SUITE_DIR`` is a directory such as
``suites/ds41f-ru/`` with a ``suite.py`` that names a corpus and fixes the model,
seed, PP schedule and TG.  The corpus decides what text is read, the suite
decides the model and schedule, and this command plus ``benchkit.py`` decide how
it is cut, checked and frozen.

The tokenizer and chat encoder come from a Maya source checkout, so run this in
a Maya image (its environment provides ``regex`` and ``jinja2``):

    MAYA_ROOT=/src python3 freeze.py freeze suites/ds41f-ru \
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

ROOT = Path(__file__).resolve().parent


def load_module(path, name, required):
    if not path.is_file():
        raise SystemExit(f'{path} not found')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for attr in required:
        if not hasattr(module, attr):
            raise SystemExit(f'{path} does not define {attr}')
    return module


def load_corpus(directory):
    return load_module(Path(directory) / 'corpus.py', 'corpus',
                       ('NAME', 'SOURCES', 'TASKS', 'TASK_LABELS', 'SOURCE_NOTE', 'LICENSE_NOTE',
                        'NOTES'))


def load_suite(directory):
    return load_module(Path(directory) / 'suite.py', 'suite', ('SUITE', 'CORPUS'))


def write_sources_md(corpus, corpus_dir, source, force):
    rows = [json.loads(s) for s in source.read_text().splitlines() if s.strip()]
    text = benchkit.sources_markdown(rows, corpus.SOURCE_NOTE, corpus.LICENSE_NOTE)
    benchkit.write_atomic(Path(corpus_dir) / 'SOURCES.md', text, force)
    print(f'{corpus_dir}/SOURCES.md: {len(rows)} articles')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    fetch = sub.add_parser('fetch', help='download the articles listed in a corpus')
    fetch.add_argument('corpus_dir', type=Path)
    fetch.add_argument('--out', type=Path, help='default: CORPUS_DIR/sources.jsonl')
    fetch.add_argument('--resume', action='store_true')

    sources = sub.add_parser('sources', help='write SOURCES.md from a frozen sources.jsonl')
    sources.add_argument('corpus_dir', type=Path)
    sources.add_argument('--source', type=Path, help='default: CORPUS_DIR/sources.jsonl')
    sources.add_argument('--force', action='store_true')

    freeze = sub.add_parser('freeze', help='cut and freeze a suite')
    freeze.add_argument('suite_dir', type=Path)
    freeze.add_argument('--source', type=Path, help="default: the corpus's sources.jsonl")
    freeze.add_argument('--out-dir', type=Path, help='default: SUITE_DIR')
    freeze.add_argument('--tokenizer', default='/data/ds4/tokenizer')
    freeze.add_argument('--maya-root', default=os.environ.get('MAYA_ROOT', '/opt/maya'))
    freeze.add_argument('--force', action='store_true')

    args = ap.parse_args()

    if args.command == 'fetch':
        corpus_dir = args.corpus_dir.resolve()
        corpus = load_corpus(corpus_dir)
        out = (args.out or corpus_dir / 'sources.jsonl').resolve()
        benchkit.fetch_articles(corpus.SOURCES, out, args.resume)
        write_sources_md(corpus, corpus_dir, out, False)
        return 0

    if args.command == 'sources':
        corpus_dir = args.corpus_dir.resolve()
        corpus = load_corpus(corpus_dir)
        source = (args.source or corpus_dir / 'sources.jsonl').resolve()
        if not source.is_file():
            raise SystemExit(f'{source} not found; run "fetch" first')
        write_sources_md(corpus, corpus_dir, source, args.force)
        return 0

    suite_dir = args.suite_dir.resolve()
    suite = load_suite(suite_dir)
    corpus_dir = (ROOT / 'corpora' / suite.CORPUS).resolve()
    if not corpus_dir.is_dir():
        raise SystemExit(f'corpus {suite.CORPUS!r} not found under {ROOT / "corpora"}')
    corpus = load_corpus(corpus_dir)
    source = (args.source or corpus_dir / 'sources.jsonl').resolve()
    out = (args.out_dir or suite_dir).resolve()
    if not source.is_file():
        raise SystemExit(f'{source} not found; run "fetch" for {corpus_dir} or point --source')
    manifest = benchkit.freeze_suite(suite.SUITE, corpus, corpus_dir, out, source,
                                     args.tokenizer, args.maya_root, args.force)
    print(json.dumps({'suite': manifest['suite'], 'corpus': manifest['corpus']['name'],
                      'cases': len(manifest['order']), 'tg': manifest['tg'],
                      'files': manifest['files']}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
