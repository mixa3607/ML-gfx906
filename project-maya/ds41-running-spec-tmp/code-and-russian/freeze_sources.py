#!/usr/bin/env python3
"""Recover the documented Russian pool, retaining the six available revisions."""
import importlib.util
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent


def main():
    spec = importlib.util.spec_from_file_location('original_corpus', ROOT.parents[1] / 'ds41-running-tmp/corpus.py')
    corpus = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(corpus)
    saved = [json.loads(line) for line in (ROOT.parent / 'sources.jsonl').read_text().splitlines()]
    retained = {d['requested_title']: d for d in saved}
    out = ROOT / 'russian-sources.jsonl'
    with out.open('x') as f:
        seen = set()
        for split in ('warmup', 'dev'):
            for title in corpus.SOURCES[split]:
                if title in retained:
                    old = retained[title]
                    row = {'split': split, 'requested_title': title, 'title': old['title'],
                           'pageid': old['pageid'], 'revision': old['revision'],
                           'url': old['revision_url'], 'license': old['rightsinfo'],
                           'sha256': old['text_sha256'], 'text': old['text'],
                           'origin': 'retained-six-page-screen'}
                else:
                    row = corpus.fetch_one((split, title))
                    row['origin'] = 'refetched-original-recipe-2026-10-26'
                    time.sleep(2)
                if row['pageid'] in seen:
                    raise ValueError(f'Duplicate or redirected page: {title}')
                seen.add(row['pageid'])
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                print(split, title, row['revision'], len(row['text']), flush=True)


if __name__ == '__main__':
    main()
