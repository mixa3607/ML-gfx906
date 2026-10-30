#!/usr/bin/env python3
"""Fetch attributed Russian source texts and slice them into DeepSeek-V4.1-Flash cases.

Two subcommands:

    fetch   download the articles listed in SOURCES into a frozen JSONL file,
            one JSON object per article (revision, URL, SHA-256, text);
    build   read that frozen file and cut requests of exact PP tokens for one
            split, writing a JSONL case file.

The suite that this directory ships (which lengths, which order, warmup vs
measurement) is defined in ``freeze_inputs.py``.  Read ``README.md`` for the
human description and ``CASES.md`` for the frozen result.

Why the cut works the way it does
---------------------------------
A request must tokenise to exactly PP tokens, including the chat template and
the generation header.  We therefore render the full user message, tokenise it,
and then cut *only source prose* off the end - never the task, the template or
the assistant header.  Source passages are consumed monotonically per article,
so no byte range is sent twice anywhere in the suite.

The actual tokenizer and chat encoder are Maya's own (``strata_tokenizer`` and
``serve.ds41_encoding``): the ids are what the engine will see, not an
approximation from another tokenizer.  Set ``MAYA_ROOT`` to a checkout of the
Maya source whose ``tools/`` and ``serve/`` directories are importable; the
container recipe in ``README.md`` does that.

Everything here is deterministic: the same frozen sources, seed, tokenizer and
encoder produce byte-identical case files (checked by re-running and comparing
SHA-256).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

MAYA_ROOT = Path(os.environ.get('MAYA_ROOT', '/opt/maya'))

# Separate articles in each split; broad domains intentionally overlap.  The
# warmup pool is distinct from the measurement pool so that a warmed cache never
# hides the cost of a measurement article.  ``holdout`` is the final-check pool:
# it is listed here for a later fetch and is deliberately absent from the
# shipped sources.jsonl, so this corpus cannot be tuned against it.
SOURCES = {
    'warmup': [
        'Фотосинтез', 'Великий шёлковый путь', 'Тепловой насос', 'Шахматы',
        'Инфляция', 'Народная музыка', 'Гражданское право', 'Сон',
        'Почва', 'Реляционная база данных', 'Северный Ледовитый океан', 'Керамика'],
    'dev': [
        'Вулкан', 'Книгопечатание', 'Электрический двигатель', 'Волейбол',
        'Страхование', 'Импрессионизм', 'Авторское право', 'Иммунная система',
        'Пчеловодство', 'Операционная система', 'Озеро Байкал', 'Бетон',
        'Спектроскопия', 'Ганзейский союз', 'Транзистор', 'Фигурное катание',
        'Логистика', 'Русская литература', 'Трудовое право', 'Пищеварение',
        'Лесоводство', 'Компилятор', 'Кавказ', 'Стекло'],
    'holdout': [
        'Тектоника плит', 'Новгородская республика', 'Литий-ионный аккумулятор', 'Плавание',
        'Облигация', 'Архитектура барокко', 'Административное право', 'Кровообращение',
        'Севооборот', 'Криптография', 'Волга', 'Бумага',
        'Радиоастрономия', 'Земская реформа', 'Ветрогенератор', 'Баскетбол',
        'Налогообложение', 'Театр', 'Семейное право', 'Зрение',
        'Виноградарство', 'Распределённая система', 'Камчатка', 'Металлургия',
        'Ледник', 'Античность', 'Полупроводник', 'Спортивное ориентирование',
        'Международная торговля', 'Симфония', 'Международное право', 'Нервная система',
        'Гидропоника', 'Алгоритм', 'Уральские горы', 'Ткачество',
        'Россия', 'Франция', 'Япония', 'Римская империя', 'Древняя Греция',
        'Эволюция', 'Термодинамика', 'Квантовая механика', 'Программирование',
        'Математический анализ', 'Русский язык', 'Астрономия']}

# Six tasks, cycled in order within each split.  The requested answer length
# encourages reaching the TG256 limit; it does not authorise ignoring natural EOS.
TASKS = [
    'Объясни содержание человеку без специальной подготовки. Разверни ответ: не менее 500 слов, с примерами и оговорками.',
    'Подготовь подробную аналитическую записку: основные положения, причинные связи, ограничения и открытые вопросы. Не менее 500 слов.',
    'Составь развёрнутый учебный диалог: собеседник сомневается, эксперт отвечает и исправляет заблуждения. Не менее 500 слов.',
    'Напиши подробный план выступления с пояснениями, примерами и ответами на возможные вопросы аудитории. Не менее 500 слов.',
    'Преобразуй материал в ясную статью для неспециалиста. Разделяй установленные факты и предположения; не менее 500 слов.',
    'Разбери материал критически: терминология, аргументы, возможные ошибки интерпретации и вопросы для проверки. Не менее 500 слов.']

# Short English labels for human-readable tables (CASES.md, README.md).
TASK_LABELS = [
    'explain to a layperson',
    'analytical memo',
    'tutorial dialogue',
    'talk plan with Q&A',
    'plain-language article',
    'critical review']


def fetch_one(item):
    split, title = item
    query = urllib.parse.urlencode({
        'action': 'query', 'prop': 'extracts|revisions', 'rvprop': 'ids',
        'explaintext': 1, 'format': 'json', 'redirects': 1, 'titles': title})
    url = 'https://ru.wikipedia.org/w/api.php?' + query
    request = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0 (Russian inference benchmark; source attribution)'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as r:
                raw = r.read(4 * 1024 * 1024 + 1)
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 2:
                raise
            delay = max(60, int(e.headers.get('Retry-After', '60')))
            print(f'Wikipedia rate limit: waiting {delay}s', file=sys.stderr, flush=True)
            time.sleep(delay)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError(f'Oversized source: {title}')
    page, = json.loads(raw)['query']['pages'].values()
    text = page.get('extract', '').strip()
    if len(text) < 1000:
        raise ValueError(f'Source too short or missing: {title}: {len(text)} characters')
    revision = page['revisions'][0]['revid']
    return {'split': split, 'requested_title': title, 'title': page['title'], 'pageid': page['pageid'],
            'revision': revision, 'url': f'https://ru.wikipedia.org/w/index.php?oldid={revision}',
            'license': 'CC BY-SA (see article history and Wikipedia terms)',
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'text': text}


def fetch_all(path, resume=False):
    if path.exists() and not resume:
        raise FileExistsError(path)
    items = [(split, title) for split, titles in SOURCES.items() for title in titles]
    existing = [json.loads(s) for s in path.read_text().splitlines()] if path.exists() else []
    seen = {(d['split'], d.get('requested_title', d['title'])) for d in existing}
    items = [item for item in items if item not in seen]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a' if resume else 'x') as f:
        for item in items:
            row = fetch_one(item)
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            f.flush()
            print(row['split'], row['title'], len(row['text']), flush=True)
            time.sleep(2)


def load_encoder(tokenizer):
    """Maya's tokenizer and DeepSeek chat encoder, from MAYA_ROOT."""
    sys.path[:0] = [str(MAYA_ROOT), str(MAYA_ROOT / 'tools')]
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate
    return Tokenizer.from_dir(tokenizer), ChatTemplate(Path(tokenizer) / 'chat_template.jinja')


def build_cases(source, split, lengths, count, seed, tokenizer, task_position='front'):
    """Return ``count`` cases whose tokenised prompts are exactly ``lengths`` long.

    ``lengths`` is cycled: ``case i`` gets ``lengths[i % len(lengths)]``, which is
    how a two-round sweep is expressed.  The cut keeps the whole assistant
    header and, with ``task_position='end'``, the question itself; only source
    prose is trimmed.  Raises if the frozen sources cannot cover a case - the
    fix is more unique articles, never padded or repeated text.
    """
    tok, template = load_encoder(tokenizer)
    documents = [json.loads(s) for s in source.read_text().splitlines() if s.strip()]
    if len({d['pageid'] for d in documents}) != len(documents):
        raise ValueError('Duplicate pages, including redirects, across corpus splits')
    docs = [d for d in documents if d['split'] == split]
    if count > len(docs):
        raise ValueError('More requests than unique lead articles; extend the corpus')
    rng = random.Random(seed)
    rng.shuffle(docs)
    tail = tok.encode('<｜Assistant｜></think>', parse_special=True)
    used = {d['pageid']: 0 for d in docs}
    by_page = {d['pageid']: d for d in docs}
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    cases = []
    for index in range(count):
        length = lengths[index % len(lengths)]
        ordered = docs[index % len(docs):] + docs[:index % len(docs)]
        ordered = [d for d in ordered if used[d['pageid']] < len(d['text'].encode())]
        if not ordered:
            raise ValueError('Source corpus exhausted; do not repeat passages to fill a test')
        pieces = [d['text'].encode()[used[d['pageid']]:].decode('utf-8', errors='ignore') for d in ordered]
        text = '\n\n'.join(d['title'] + '\n' + piece for d, piece in zip(ordered, pieces))
        task_index = index % len(TASKS)
        task = TASKS[task_index]
        if task_position == 'end':
            content = ordered[0]['title'] + '\n\nМатериалы:\n' + text + '\n\n' + task
            suffix = tok.encode('\n\n' + task + '<｜Assistant｜></think>', parse_special=True)
        else:
            content = ordered[0]['title'] + '. ' + task + '\n\nМатериалы:\n' + text
            suffix = tail
        rendered = template.render([{'role': 'user', 'content': content}], reasoning_effort='none')
        ids = tok.encode(rendered, parse_special=True)
        if ids[-len(tail):] != tail:
            raise ValueError('Unexpected DeepSeek chat template suffix')
        if len(ids) < length:
            raise ValueError(f'{split}: {len(ids)} tokens available, need {length}; add unique source articles')
        # Cut only source material, retaining the question (when at the end)
        # and the complete assistant header.  Never pad with repeated source text.
        ids = ids[:length - len(suffix)] + suffix
        body_start = len(rendered[:rendered.index(text)].encode())
        body_bytes = sum(len(tok.token_bytes(t)) for t in ids[:-len(suffix)]) - body_start
        passages = []
        articles = []
        for doc, piece in zip(ordered, pieces):
            header = len((doc['title'] + '\n').encode())
            available = len(piece.encode())
            consumed = max(0, min(available, body_bytes - header))
            if consumed:
                start = used[doc['pageid']]
                skipped = len(doc['text'].encode()) - start - len(piece.encode())
                # A cut may land inside a UTF-8 character. The next request drops
                # incomplete leading bytes, never reuses the previous passage.
                used[doc['pageid']] += skipped + consumed
                passages.append({'pageid': doc['pageid'], 'start_byte': start,
                                 'end_byte': used[doc['pageid']]})
                articles.append({'pageid': doc['pageid'], 'title': doc['title'],
                                 'revision': doc['revision'], 'url': doc['url'],
                                 'start_byte': start, 'end_byte': used[doc['pageid']],
                                 'bytes': used[doc['pageid']] - start})
            body_bytes -= header + available + 2
            if body_bytes <= 0:
                break
        if not passages:
            raise ValueError('No actual source passage fits the prompt')
        case_id = f'{split}-{seed}-{index:02d}-pp{length}' + ('-end' if task_position == 'end' else '')
        cases.append({'id': case_id, 'phase': split, 'task_position': task_position,
                      'seed': seed, 'pp': length, 'lead_title': ordered[0]['title'],
                      'task_index': task_index + 1, 'task_label': TASK_LABELS[task_index], 'task': task,
                      'source_sha256': source_hash, 'passages': passages, 'articles': articles,
                      'prompt_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(), 'ids': ids})
    if len({tuple(c['ids']) for c in cases}) != len(cases):
        raise ValueError('Duplicate requests')
    return cases


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('fetch', help='download the articles listed in SOURCES')
    f.add_argument('--out', type=Path, required=True)
    f.add_argument('--resume', action='store_true')
    b = sub.add_parser('build', help='write cases for one split')
    b.add_argument('--source', type=Path, required=True)
    b.add_argument('--out', type=Path, required=True)
    b.add_argument('--split', choices=SOURCES, required=True)
    b.add_argument('--pp', type=int, nargs='+', default=[2048])
    b.add_argument('--count', type=int, required=True)
    b.add_argument('--seed', type=int, default=20261024)
    b.add_argument('--tokenizer', default='/data/ds4/tokenizer')
    b.add_argument('--task-position', choices=['front', 'end'], default='front')
    a = p.parse_args()
    if a.command == 'fetch':
        fetch_all(a.out, a.resume)
        return 0
    if any(n <= 0 or n % 2048 or n + 256 > 196608 for n in a.pp):
        p.error('PP must be a positive multiple of 2048 and leave room for TG256')
    if a.count <= 0:
        p.error('--count must be positive')
    cases = build_cases(a.source, a.split, a.pp, a.count, a.seed, a.tokenizer, a.task_position)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open('x') as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    print(f'{a.out}: {len(cases)} requests, PP {a.pp}, seed {a.seed}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
