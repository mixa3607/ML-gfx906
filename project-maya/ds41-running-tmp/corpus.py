#!/usr/bin/env python3
"""Fetch attributed Russian source texts locally, then tokenize cases inside Maya."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


# Separate articles in each split; broad domains intentionally overlap.
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

TASKS = [
    'Объясни содержание человеку без специальной подготовки. Разверни ответ: не менее 500 слов, с примерами и оговорками.',
    'Подготовь подробную аналитическую записку: основные положения, причинные связи, ограничения и открытые вопросы. Не менее 500 слов.',
    'Составь развёрнутый учебный диалог: собеседник сомневается, эксперт отвечает и исправляет заблуждения. Не менее 500 слов.',
    'Напиши подробный план выступления с пояснениями, примерами и ответами на возможные вопросы аудитории. Не менее 500 слов.',
    'Преобразуй материал в ясную статью для неспециалиста. Разделяй установленные факты и предположения; не менее 500 слов.',
    'Разбери материал критически: терминология, аргументы, возможные ошибки интерпретации и вопросы для проверки. Не менее 500 слов.']


def fetch_one(item):
    split, title = item
    query = urllib.parse.urlencode({
        'action': 'query', 'prop': 'extracts|revisions', 'rvprop': 'ids',
        'explaintext': 1, 'format': 'json', 'redirects': 1, 'titles': title})
    url = 'https://ru.wikipedia.org/w/api.php?' + query
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Russian inference benchmark; source attribution)'})
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


def build_cases(source, output, split, lengths, count, seed, tokenizer, task_position='front'):
    sys.path[:0] = ['/opt/maya', '/opt/maya/tools']
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate

    tok = Tokenizer.from_dir(tokenizer)
    template = ChatTemplate(Path(tokenizer) / 'chat_template.jinja')
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
        task = TASKS[index % len(TASKS)]
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
        # and the complete assistant header. Never pad with repeated source text.
        ids = ids[:length - len(suffix)] + suffix
        body_start = len(rendered[:rendered.index(text)].encode())
        body_bytes = sum(len(tok.token_bytes(t)) for t in ids[:-len(suffix)]) - body_start
        passages = []
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
            body_bytes -= header + available + 2
            if body_bytes <= 0:
                break
        if not passages:
            raise ValueError('No actual source passage fits the prompt')
        case_id = f'{split}-{seed}-{index:02d}-pp{length}' + ('-end' if task_position == 'end' else '')
        cases.append({'id': case_id, 'phase': split, 'task_position': task_position,
                      'seed': seed, 'pp': length, 'lead_title': ordered[0]['title'],
                      'source_sha256': source_hash, 'passages': passages,
                      'prompt_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(), 'ids': ids})
    if len({tuple(c['ids']) for c in cases}) != len(cases):
        raise ValueError('Duplicate requests')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as f:
        for case in cases:
            f.write(json.dumps(case, ensure_ascii=False) + '\n')
    print(f'{output}: {len(cases)} requests, PP {lengths}, seed {seed}')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    f = sub.add_parser('fetch')
    f.add_argument('--out', type=Path, required=True)
    f.add_argument('--resume', action='store_true')
    b = sub.add_parser('build')
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
    else:
        if any(n <= 0 or n % 2048 or n + 256 > 196608 for n in a.pp):
            p.error('PP must be a positive multiple of 2048 and leave room for TG256')
        if a.count <= 0:
            p.error('--count must be positive')
        build_cases(a.source, a.out, a.split, a.pp, a.count, a.seed, a.tokenizer, a.task_position)


if __name__ == '__main__':
    main()
