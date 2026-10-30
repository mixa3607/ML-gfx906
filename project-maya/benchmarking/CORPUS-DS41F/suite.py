#!/usr/bin/env python3
"""The DS4.1F suite: what is measured, and from which frozen prose.

This file is the part that is specific to DeepSeek-V4.1-Flash on Maya: the
article pools, the six Russian tasks, the seed, the PP schedule, the TG budget
and the pinned chat encoder.  The shared machinery - fetching, exact-length
cutting, checks and the generated manifest - is in ``../benchkit.py``.

The 12 warmups are shared with ``project-maya/ds41-pr592``; the measurement
sweep is new (PP 2K-32K).  ``warmup_reference_sha`` proves the warmups still
match that older suite while freezing.
"""
from benchkit import PROTOCOL

SUITE = {
    'name': 'ds41f-warm-cache-pp2k-32k',
    'model': 'deepseek-v4.1-flash',
    'purpose': 'warm-cache prefill and decode throughput, one request at a time',
    'seed': 20261024,
    'tg': 256,
    'warmup': {'split': 'warmup', 'pp': 2048, 'count': 12},
    'measurement': {'split': 'dev', 'pp': [2048, 4096, 8192, 16384, 32768], 'rounds': 2},
    'task_position': 'front',
    # Maya's DeepSeek chat encoder, with thinking off, ends the user turn with
    # the assistant header and a closed think block.
    'assistant_suffix': '<｜Assistant｜></think>',
    'render_kwargs': {'reasoning_effort': 'none'},
    'bos_text': '<｜begin▁of▁sentence｜>',
    'encoder': {'project': 'project-maya', 'tag': 'v1.1.38',
                'commit': 'cf6472cc84489765791ad97bb55b395e8f442088'},
    'warmup_reference_sha': '1429132bb086e222f8c578ef8c852712a05aaaafad09094fcdc5fedfad10a7c2',
    'protocol': PROTOCOL + [
        'Baseline: approximate prompt skips off, dense and expert precision unmodified.',
    ],
    'source_note': 'Russian Wikipedia prose, frozen at the listed revision.',
    'license_note': 'License: CC BY-SA; follow the article history and Wikipedia terms when '
                    'redistributing excerpts. Medical and legal texts are performance inputs, '
                    'not advice.',
    'notes': [
        'The 12 warmups are identical to project-maya/ds41-pr592 (same pool, seed and PP).',
        'Sources are frozen Russian Wikipedia prose: page id, revision, URL and SHA-256 per article.',
        'The dev pool was used by earlier Maya tuning; this is a baseline corpus, not a blind holdout.',
        'The holdout article list here is intentionally not part of sources.jsonl.',
        'PP is the complete tokenised input; only source prose is cut to reach it.',
        'TG256 is a request parameter, not part of the frozen files.',
        'README.md is documentation; it is not covered by the file hashes in the manifest.',
    ],
}

# Separate articles in each split; broad domains intentionally overlap.  The
# warmup pool is distinct from the measurement pool so that a warmed cache never
# hides the cost of a measurement article.  ``holdout`` is the final-check pool:
# it is listed for a later fetch and deliberately absent from the shipped
# sources.jsonl, so this suite cannot be tuned against it.
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
