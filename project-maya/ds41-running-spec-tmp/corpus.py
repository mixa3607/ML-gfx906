#!/usr/bin/env python3
"""Freeze a small attributed Wikipedia corpus and six PP2048 cases."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import urllib.parse
import urllib.request

POOL = {
    'warmup': ['Фотосинтез', 'Великий шёлковый путь', 'Тепловой насос'],
    'measurement': ['Вулкан', 'Книгопечатание', 'Электрический двигатель'],
}
TASKS = [
    'Объясни содержание человеку без специальной подготовки. Разверни ответ: не менее 500 слов, с примерами и оговорками.',
    'Подготовь подробную аналитическую записку: основные положения, причинные связи, ограничения и открытые вопросы. Не менее 500 слов.',
    'Составь развёрнутый учебный диалог: собеседник сомневается, эксперт отвечает и исправляет заблуждения. Не менее 500 слов.',
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fetch(out):
    with out.open('x') as f:
        for phase, titles in POOL.items():
            for title in titles:
                query = urllib.parse.urlencode({
                    'action': 'query', 'prop': 'extracts|revisions', 'rvprop': 'ids',
                    'explaintext': 1, 'format': 'json', 'redirects': 1, 'titles': title,
                    'meta': 'siteinfo', 'siprop': 'rightsinfo',
                })
                req = urllib.request.Request('https://ru.wikipedia.org/w/api.php?' + query,
                                             headers={'User-Agent': 'ML-gfx906-benchmark/1.0 (Wikipedia attribution)'})
                with urllib.request.urlopen(req, timeout=90) as response:
                    data = json.load(response)
                page, = data['query']['pages'].values()
                text = page['extract'].strip()
                if len(text) < 5000:
                    raise ValueError(f'Source too short: {title}')
                row = {'phase': phase, 'requested_title': title, 'title': page['title'],
                       'pageid': page['pageid'], 'revision': page['revisions'][0]['revid'],
                       'text': text, 'text_sha256': digest(text.encode()),
                       'rightsinfo': data['query']['rightsinfo'],
                       'revision_url': f'https://ru.wikipedia.org/w/index.php?oldid={page["revisions"][0]["revid"]}',
                       'attribution_url': 'https://ru.wikipedia.org/w/index.php?' + urllib.parse.urlencode(
                           {'title': page['title'], 'action': 'history'})}
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                print(phase, title, len(text), flush=True)
                time.sleep(2)


def build(source, out, tokenizer):
    sys.path[:0] = ['/opt/maya', '/opt/maya/tools']
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate

    tok = Tokenizer.from_dir(tokenizer)
    template = ChatTemplate(Path(tokenizer) / 'chat_template.jinja')
    documents = [json.loads(line) for line in source.read_text().splitlines()]
    if len(documents) != 6 or len({d['pageid'] for d in documents}) != 6:
        raise ValueError('Six different pages required')
    seed = 20261026
    rng = random.Random(seed)
    suffix = tok.encode('<｜Assistant｜></think>', parse_special=True)
    cases = []
    order = {}
    for phase in POOL:
        docs = [d for d in documents if d['phase'] == phase]
        rng.shuffle(docs)
        order[phase] = [d['pageid'] for d in docs]
        for index, doc in enumerate(docs):
            prefix = doc['title'] + '. ' + TASKS[index] + '\n\nМатериалы:\n' + doc['title'] + '\n'
            rendered = template.render([{'role': 'user', 'content': prefix + doc['text']}], reasoning_effort='none')
            ids = tok.encode(rendered, parse_special=True)
            if ids[-len(suffix):] != suffix or len(ids) < 2048:
                raise ValueError('Unexpected template or insufficient unique source text')
            ids = ids[:2048 - len(suffix)] + suffix
            body_start = len(rendered[:rendered.index(doc['text'])].encode())
            body_bytes = sum(len(tok.token_bytes(t)) for t in ids[:-len(suffix)]) - body_start
            if not 0 < body_bytes <= len(doc['text'].encode()):
                raise ValueError('Source passage accounting failed')
            rendered_bytes = b''.join(tok.token_bytes(t) for t in ids)
            cases.append({'id': f'{phase}-{index + 1}', 'phase': phase, 'pp': 2048,
                          'seed': seed, 'lead_title': doc['title'], 'thinking': 'none',
                          'rendered_text': rendered_bytes.decode('utf-8', errors='replace'),
                          'rendered_bytes_hex': rendered_bytes.hex(),
                          'passages': [{'pageid': doc['pageid'], 'start_byte': 0, 'end_byte': body_bytes,
                                        'revision_url': doc['revision_url'], 'text_sha256': doc['text_sha256']}],
                          'ids_sha256': digest(json.dumps(ids).encode()), 'ids': ids})
    if len({tuple(c['ids']) for c in cases}) != 6:
        raise ValueError('Duplicate prompts')
    with out.open('x') as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    manifest = {'seed': seed, 'ordered_pageids': order, 'cases_sha256': digest(out.read_bytes()),
                'sources_sha256': digest(source.read_bytes()), 'count': 6, 'pp': 2048,
                'tokenizer_files': {p.name: digest(p.read_bytes()) for p in Path(tokenizer).iterdir() if p.is_file()}}
    out.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'build'])
    parser.add_argument('--source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tokenizer', default='/data/ds4/tokenizer')
    args = parser.parse_args()
    if args.command == 'fetch':
        fetch(args.out)
    else:
        build(args.source, args.out, args.tokenizer)
