#!/usr/bin/env python3
"""Fetch corpus articles or build tokenised benchmark requests."""

import argparse
import importlib.util
import json
import random
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def load_config(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch(corpus_dir):
    corpus = load_config(corpus_dir / 'corpus.py')
    with (corpus_dir / 'sources.jsonl').open('x') as output:
        for split, titles in corpus.ARTICLE_TITLES.items():
            for title in titles:
                query = urllib.parse.urlencode({
                    'action': 'query',
                    'prop': 'extracts|revisions',
                    'rvprop': 'ids',
                    'explaintext': 1,
                    'format': 'json',
                    'redirects': 1,
                    'titles': title,
                })
                request = urllib.request.Request(
                    'https://ru.wikipedia.org/w/api.php?' + query,
                    headers={'User-Agent': 'ML-gfx906 benchmark corpus'},
                )
                with urllib.request.urlopen(request, timeout=90) as response:
                    page, = json.load(response)['query']['pages'].values()
                text = page['extract'].strip()
                if not text:
                    raise ValueError(f'Empty Wikipedia article: {title}')
                revision = page['revisions'][0]['revid']
                article = {
                    'split': split,
                    'title': page['title'],
                    'pageid': page['pageid'],
                    'revision': revision,
                    'url': f'https://ru.wikipedia.org/w/index.php?oldid={revision}',
                    'license': 'CC BY-SA (see article history and Wikipedia terms)',
                    'text': text,
                }
                output.write(json.dumps(article, ensure_ascii=False) + '\n')
                output.flush()
                print(split, article['title'], flush=True)
                time.sleep(2)


def build_cases(sources, instructions, suite, tokenizer, template):
    suffix = tokenizer.encode(suite.ASSISTANT_SUFFIX, parse_special=True)
    phases = (
        ('warmup', 'warmup', suite.WARMUP_PP),
        ('measurement', 'dev', suite.MEASUREMENT_PP),
    )
    for phase, split, lengths in phases:
        documents = [doc for doc in sources if doc['split'] == split]
        random.Random(suite.SEED).shuffle(documents)
        offsets = {doc['pageid']: 0 for doc in documents}
        for index, pp in enumerate(lengths):
            lead = index % len(documents)
            ordered = documents[lead:] + documents[:lead]
            ordered = [doc for doc in ordered if offsets[doc['pageid']] < len(doc['text'].encode())]
            pieces = [
                doc['text'].encode()[offsets[doc['pageid']]:].decode('utf-8', errors='ignore')
                for doc in ordered
            ]
            material = '\n\n'.join(
                doc['title'] + '\n' + piece for doc, piece in zip(ordered, pieces)
            )
            if not material:
                raise ValueError(f'{phase}: source corpus exhausted at request {index}')
            instruction = instructions[index % len(instructions)]
            content = ordered[0]['title'] + '. ' + instruction + '\n\nМатериалы:\n' + material
            rendered = template.render([{'role': 'user', 'content': content}], **suite.RENDER_KWARGS)
            ids = tokenizer.encode(rendered, parse_special=True)
            if ids[-len(suffix):] != suffix:
                raise ValueError('Chat template does not end with ASSISTANT_SUFFIX')
            if len(ids) < pp:
                raise ValueError(f'{phase}: need {pp} tokens, only {len(ids)} available')

            # Keep the instruction and assistant header; cut only the source prose.
            ids = ids[:pp - len(suffix)] + suffix
            body_start = len(rendered[:rendered.index(material)].encode())
            body_bytes = sum(len(tokenizer.token_bytes(token)) for token in ids[:-len(suffix)]) - body_start
            passages = []
            for doc, piece in zip(ordered, pieces):
                header_bytes = len((doc['title'] + '\n').encode())
                available = len(piece.encode())
                consumed = max(0, min(available, body_bytes - header_bytes))
                if consumed:
                    start = len(doc['text'].encode()) - available
                    end = start + consumed
                    offsets[doc['pageid']] = end
                    passages.append({'pageid': doc['pageid'], 'start_byte': start, 'end_byte': end})
                body_bytes -= header_bytes + available + 2
                if body_bytes <= 0:
                    break
            if not passages:
                raise ValueError(f'{phase}: PP{pp} leaves no room for source prose')
            yield {
                'id': f'{phase}-{index:02d}-pp{pp}',
                'phase': phase,
                'pp': pp,
                'tg': suite.TG,
                'passages': passages,
                'ids': ids,
                'prompt': tokenizer.decode(ids),
            }


def freeze(suite_dir, tokenizer_dir, maya_root, output):
    suite = load_config(suite_dir / 'suite.py')
    corpus_dir = ROOT / 'corpora' / suite.CORPUS
    corpus = load_config(corpus_dir / 'corpus.py')
    sources = [json.loads(line) for line in (corpus_dir / 'sources.jsonl').read_text().splitlines()]
    pageids = [doc['pageid'] for doc in sources]
    if len(set(pageids)) != len(pageids):
        raise ValueError('Corpus contains duplicate Wikipedia pages (possibly redirects)')

    sys.path[:0] = [str(maya_root), str(maya_root / 'tools')]
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate

    tokenizer = Tokenizer.from_dir(tokenizer_dir)
    template = ChatTemplate(tokenizer_dir / 'chat_template.jinja')
    cases = list(build_cases(sources, corpus.INSTRUCTIONS, suite, tokenizer, template))
    output.write_text(''.join(json.dumps(case, ensure_ascii=False) + '\n' for case in cases))
    print(f'{output}: {len(cases)} requests')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    fetch_parser = commands.add_parser('fetch', help='download a corpus to sources.jsonl')
    fetch_parser.add_argument('corpus_dir', type=Path)
    freeze_parser = commands.add_parser('freeze', help='build cases.jsonl from a corpus and suite')
    freeze_parser.add_argument('suite_dir', type=Path)
    freeze_parser.add_argument('--tokenizer', type=Path, required=True)
    freeze_parser.add_argument('--maya-root', type=Path, required=True)
    freeze_parser.add_argument('--output', type=Path, help='default: SUITE_DIR/cases.jsonl (overwritten)')
    args = parser.parse_args()
    if args.command == 'fetch':
        fetch(args.corpus_dir)
    else:
        freeze(
            args.suite_dir,
            args.tokenizer,
            args.maya_root.resolve(),
            args.output or args.suite_dir / 'cases.jsonl',
        )


if __name__ == '__main__':
    main()
