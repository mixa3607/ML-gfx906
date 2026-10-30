#!/usr/bin/env python3
"""Shared kit: turn frozen prose into exact-length benchmark suites.

A suite lives in its own directory (``CORPUS-XXXX/``) and provides:

    suite.py    a ``SUITE`` dict and the ``SOURCES`` / ``TASKS`` / ``TASK_LABELS``
                that make it specific: article pools, task texts, seed, PP
                schedule, TG, encoder pin, model-specific tokenizer settings.

``freeze.py`` is the command-line entry point; this module holds the parts that
are the same for every suite:

    fetch_articles()   download attributed articles from the Wikipedia API;
    build_cases()      cut prose into requests of exactly PP tokens;
    freeze_suite()     write cases.jsonl, suite.json, CASES.md, SOURCES.md and
                       cases.manifest.json, with the checks that make them
                       trustworthy.

The test for "generic" here is simple: nothing in this file knows a model name,
an article title, a task text, a token or a PP length.  A suite that needs a
different chat encoder or assistant header supplies its own strings and
imports, so the cutting and freezing rules stay identical across suites.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ------------------------------------------------------------------------------------- sources
def fetch_one(split, title):
    """One article as a frozen record: revision, URL, text hash and text."""
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


def fetch_articles(pools, out, resume=False):
    """Download every title in ``pools`` (split -> titles) into ``out`` as JSONL."""
    if out.exists() and not resume:
        raise FileExistsError(out)
    items = [(split, title) for split, titles in pools.items() for title in titles]
    existing = [json.loads(s) for s in out.read_text().splitlines()] if out.exists() else []
    seen = {(d['split'], d.get('requested_title', d['title'])) for d in existing}
    items = [item for item in items if item not in seen]
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('a' if resume else 'x') as f:
        for split, title in items:
            row = fetch_one(split, title)
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
            f.flush()
            print(row['split'], row['title'], len(row['text']), flush=True)
            time.sleep(2)


# ------------------------------------------------------------------------------------- cases
def load_encoder(maya_root, tokenizer_dir):
    """Maya's byte-level tokenizer and chat template from the pinned source."""
    maya_root = Path(maya_root)
    sys.path[:0] = [str(maya_root), str(maya_root / 'tools')]
    from strata_tokenizer import Tokenizer
    from serve.frontend import ChatTemplate
    return Tokenizer.from_dir(tokenizer_dir), ChatTemplate(Path(tokenizer_dir) / 'chat_template.jinja')


def build_cases(source, split, lengths, count, seed, tok, template, suite, tasks, task_labels,
                task_position='front'):
    """Return ``count`` cases whose tokenised prompts are exactly ``lengths`` long.

    ``lengths`` is cycled: ``case i`` gets ``lengths[i % len(lengths)]``, which is
    how a two-round sweep is expressed.  A request keeps the whole assistant
    header and, with ``task_position='end'``, the question itself; only source
    prose is trimmed.  Raises if the frozen sources cannot cover a case - the
    fix is more unique articles, never padded or repeated text.
    """
    documents = [json.loads(s) for s in source.read_text().splitlines() if s.strip()]
    if len({d['pageid'] for d in documents}) != len(documents):
        raise ValueError('Duplicate pages, including redirects, across corpus splits')
    docs = [d for d in documents if d['split'] == split]
    if count > len(docs):
        raise ValueError('More requests than unique lead articles; extend the corpus')
    rng = random.Random(seed)
    rng.shuffle(docs)
    tail = tok.encode(suite['assistant_suffix'], parse_special=True)
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
        task_index = index % len(tasks)
        task = tasks[task_index]
        if task_position == 'end':
            content = ordered[0]['title'] + '\n\nМатериалы:\n' + text + '\n\n' + task
            suffix = tok.encode('\n\n' + task + suite['assistant_suffix'], parse_special=True)
        else:
            content = ordered[0]['title'] + '. ' + task + '\n\nМатериалы:\n' + text
            suffix = tail
        rendered = template.render([{'role': 'user', 'content': content}], **suite['render_kwargs'])
        ids = tok.encode(rendered, parse_special=True)
        if ids[-len(tail):] != tail:
            raise ValueError('The rendered prompt does not end with the expected assistant header')
        if len(ids) < length:
            raise ValueError(f'{split}: {len(ids)} tokens available, need {length}; add unique source articles')
        # Cut only source material, retaining the question (when at the end)
        # and the complete assistant header.  Never pad with repeated source text.
        ids = ids[:length - len(suffix)] + suffix
        body_start = len(rendered[:rendered.index(text)].encode())
        body_bytes = sum(len(tok.token_bytes(t)) for t in ids[:-len(suffix)]) - body_start
        passages, articles = [], []
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
                      'task_index': task_index + 1, 'task_label': task_labels[task_index], 'task': task,
                      'source_sha256': source_hash, 'passages': passages, 'articles': articles,
                      'prompt_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(), 'ids': ids})
    if len({tuple(c['ids']) for c in cases}) != len(cases):
        raise ValueError('Duplicate requests')
    return cases


def check_cases(cases, sources, split):
    """Reject wrong lengths, repeated requests and reused source byte ranges."""
    documents = [json.loads(s) for s in sources.read_text().splitlines() if s.strip()]
    by_page = {d['pageid']: d for d in documents}
    assert len(by_page) == len(documents), 'duplicate source pages'
    assert len({tuple(c['ids']) for c in cases}) == len(cases), 'duplicate requests'
    used = {}
    for case in cases:
        assert len(case['ids']) == case['pp'], (case['id'], len(case['ids']), case['pp'])
        assert case['ids'][0] == 0, (case['id'], 'does not start with BOS')
        for p in case['passages']:
            doc = by_page[p['pageid']]
            assert 0 <= p['start_byte'] < p['end_byte'] <= len(doc['text'].encode()), (case['id'], p)
            key = (split, p['pageid'])
            assert p['start_byte'] >= used.get(key, 0), (case['id'], 'reuses a source range', p)
            used[key] = p['end_byte']


# ------------------------------------------------------------------------------------- docs
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def render_text(tok, ids):
    """Exact prompt text; falls back to replacement if the cut split a character."""
    raw = b''.join(tok.token_bytes(t) for t in ids)
    try:
        return raw.decode('utf-8'), True
    except UnicodeDecodeError:
        return raw.decode('utf-8', 'replace'), False


def markdown_preview(text, limit=320):
    """First characters of the prompt with the line structure kept visible."""
    body = re.sub(r'[ \t]*\n[ \t\n]*', ' ⏎ ', text)
    body = re.sub(r'[ \t]+', ' ', body)
    return body[:limit] + ('…' if len(body) > limit else '')


def cases_markdown(cases, tg):
    warm = [c for c in cases if c['phase'] == 'warmup']
    measured = [c for c in cases if c['phase'] != 'warmup']
    sizes = []
    for c in measured:
        if c['pp'] not in sizes:
            sizes.append(c['pp'])
    rounds = len(measured) // len(sizes) if sizes else 0
    warm_pp = sorted({c['pp'] for c in warm})
    intro = (f'{len(cases)} requests: {len(warm)} unscored warmups at '
             f'PP{", ".join(map(str, warm_pp))}, then {len(measured)} scored measurements in '
             f'{rounds} round{"s" if rounds != 1 else ""} '
             f'({" -> ".join(map(str, sizes))} each). Every request asks for TG{tg}.')
    out = [
        '# Suite cases',
        '',
        intro,
        '',
        'PP is the complete tokenised input, including the chat template and the assistant '
        'header. The task is in front of the material; the source prose is cut only at the end '
        'so the token count is exact. See `README.md` for this suite and the parent directory '
        'for the measurement protocol; `suite.json` is the machine-readable order.',
        '',
        'In the previews, `⏎` marks a line break and the `<｜...｜>` sequences are the chat '
        'template tokens that the engine actually receives.',
        '',
        '## Feed order',
        '',
        '| # | id | phase | PP | lead article | task |',
        '| ---: | --- | --- | ---: | --- | --- |',
    ]
    for n, c in enumerate(cases, 1):
        phase = 'warmup (unscored)' if c['phase'] == 'warmup' else 'measurement'
        out.append(f"| {n} | `{c['id']}` | {phase} | {c['pp']} | {c['lead_title']} | "
                   f"{c['task_index']}. {c['task_label']} |")
    out += ['', '## Case details', '']
    for n, c in enumerate(cases, 1):
        articles = ', '.join(f"{a['title']} (rev {a['revision']}, {a['bytes']:,} B)" for a in c['articles'])
        out += [
            f"### {n}. `{c['id']}`",
            '',
            f"- Phase: **{c['phase']}**" + (' (not scored: it warms the cache)' if c['phase'] == 'warmup' else ''),
            f"- Exact input length: **PP {c['pp']}** tokens; target output: **TG {tg}** tokens",
            f"- Lead article: **{c['lead_title']}**",
            f"- Task {c['task_index']}/{len({x['task_index'] for x in cases})} "
            f"({c['task_label']}): {c['task']}",
            f"- Source passages: {articles}",
            f"- Prompt SHA-256: `{c['prompt_sha256']}`",
            f"- Prompt begins: \"{markdown_preview(c['rendered_text'])}\"",
            '',
        ]
    return '\n'.join(out)


def sources_markdown(documents, source_note, license_note):
    out = [
        '# Source articles',
        '',
        f'{source_note} The full text is in `sources.jsonl`; this table is for reading and '
        'attribution.',
        '',
        '| split | article | bytes | revision | text SHA-256 |',
        '| --- | --- | ---: | --- | --- |',
    ]
    for d in documents:
        out.append(f"| {d['split']} | {d['title']} | {len(d['text'].encode()):,} | "
                   f"[{d['revision']}]({d['url']}) | `{d['sha256'][:16]}` |")
    out += ['', license_note, '']
    return '\n'.join(out)


# ------------------------------------------------------------------------------------- freeze
# The measurement rules are the same for every suite; a suite may append its
# own lines with ``protocol = PROTOCOL + [...]`` in suite.py.
PROTOCOL = [
    'Load the model once and keep the process alive for the whole suite.',
    'Send every warmup request in file order at the suite TG; do not score them.',
    'In the same process, send the measurement requests in file order at the suite TG.',
    'One request at a time, greedy, speculation off, approximate skips off.',
    'Zero cross-request prefix/KV reuse; ordinary KV caching inside one generation stays.',
    'Do not reload the model, clear its caches or change placement settings between phases.',
    'Keep incomplete requests; a natural EOS before the TG budget is not a completed sample.',
]


def write_atomic(path, text, force):
    if Path(path).exists() and not force:
        raise FileExistsError(f'{path} exists; pass --force to regenerate')
    Path(path).write_text(text)


def freeze_suite(suite, tasks, task_labels, out, source, tokenizer, maya_root, force=False):
    """Build the configured phases and write every generated file.

    ``suite`` is the dict from the suite directory's ``suite.py``; ``out`` is
    that directory.  Returns the manifest.
    """
    out = Path(out)
    source = Path(source)
    tok, template = load_encoder(maya_root, tokenizer)
    if tok.token_bytes(0).decode() != suite['bos_text']:
        raise SystemExit(f"Token zero is not {suite['bos_text']!r}")
    warm_cfg, meas_cfg = suite['warmup'], suite['measurement']
    warmup = build_cases(source, warm_cfg['split'], [warm_cfg['pp']], warm_cfg['count'], suite['seed'],
                         tok, template, suite, tasks, task_labels, suite['task_position'])
    lengths = meas_cfg['pp'] * meas_cfg['rounds']
    measurement = build_cases(source, meas_cfg['split'], lengths, len(lengths), suite['seed'],
                              tok, template, suite, tasks, task_labels, suite['task_position'])
    if suite.get('warmup_reference_sha') and warmup[0]['prompt_sha256'] != suite['warmup_reference_sha']:
        raise SystemExit('Warmup prompts differ from the frozen reference; the pipe changed')
    check_cases(warmup, source, warm_cfg['split'])
    check_cases(measurement, source, meas_cfg['split'])

    rows, inexact = [], []
    for case in warmup + measurement:
        case = dict(case)
        case['phase'] = 'warmup' if case['phase'] == 'warmup' else 'measurement'
        case['ctx'] = case['pp']
        text, exact = render_text(tok, case['ids'])
        if exact and tok.encode(text, parse_special=True) != case['ids']:
            raise SystemExit(f"{case['id']}: rendered text does not tokenise back to its ids")
        if not exact:
            inexact.append(case['id'])
        case['rendered_text'] = text
        case['rendered_text_exact'] = exact
        rows.append(case)

    steps = [{'step': n, 'id': r['id'], 'phase': r['phase'],
              'scored': r['phase'] == 'measurement', 'pp': r['pp'], 'tg': suite['tg'],
              'lead_title': r['lead_title'], 'task_index': r['task_index'],
              'task_label': r['task_label'], 'prompt_sha256': r['prompt_sha256']}
             for n, r in enumerate(rows, 1)]
    tokenizer_files = {p.name: sha(p) for p in sorted(Path(tokenizer).iterdir()) if p.is_file()}
    doc = {'suite': suite['name'], 'model': suite['model'], 'seed': suite['seed'], 'tg': suite['tg'],
           'encoder': suite['encoder'],
           'warmup': {'pp': warm_cfg['pp'], 'count': warm_cfg['count'], 'split': warm_cfg['split'],
                      'scored': False},
           'measurement': {'pp': meas_cfg['pp'], 'rounds': meas_cfg['rounds'],
                           'count': len(lengths), 'split': meas_cfg['split'], 'scored': True},
           'tokenizer_files': tokenizer_files, 'steps': steps}
    sources = [json.loads(s) for s in source.read_text().splitlines() if s.strip()]

    write_atomic(out / 'cases.jsonl',
                 ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), force)
    write_atomic(out / 'suite.json', json.dumps(doc, ensure_ascii=False, indent=2) + '\n', force)
    write_atomic(out / 'CASES.md', cases_markdown(rows, suite['tg']), force)
    write_atomic(out / 'SOURCES.md', sources_markdown(sources, suite['source_note'],
                                                         suite['license_note']), force)

    kit_dir = Path(__file__).resolve().parent
    local = ('cases.jsonl', 'suite.json', 'CASES.md', 'SOURCES.md', 'suite.py')
    manifest = {
        'suite': suite['name'],
        'model': suite['model'],
        'purpose': suite['purpose'],
        'seed': suite['seed'],
        'tg': suite['tg'],
        'order': [s['id'] for s in steps],
        'protocol': suite.get('protocol', PROTOCOL),
        'encoder': suite['encoder'],
        'sources': {'file': 'sources.jsonl', 'sha256': sha(source),
                    'articles': {split: sum(1 for d in sources if d['split'] == split)
                                 for split in sorted({d['split'] for d in sources})}},
        'tokenizer_files': tokenizer_files,
        'files': {name: sha(out / name) for name in local},
        'kit': {'benchkit.py': sha(kit_dir / 'benchkit.py'), 'freeze.py': sha(kit_dir / 'freeze.py')},
        'generator': f'python3 freeze.py {out.name} --source {source.name}',
        'rendered_text_exact': not inexact,
        'rendered_text_inexact_cases': inexact,
        'notes': suite['notes'],
    }
    write_atomic(out / 'cases.manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n',
                 force)
    return manifest
