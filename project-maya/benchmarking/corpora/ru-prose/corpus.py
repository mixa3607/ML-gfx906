#!/usr/bin/env python3
"""The ``ru-prose`` corpus: Russian Wikipedia prose and six writing tasks.

A corpus is model-independent.  It defines *what text* a suite reads and *what
is asked about it*: the article pools, the tasks, the attribution notes and the
frozen ``sources.jsonl`` next to this file.  It says nothing about which model,
tokenizer, chat template or PP schedule is used - that is a suite
(``../suites/``).

The pools are deliberately split:

    warmup   12 articles used only by warmup requests;
    dev      24 articles used by measured requests;
    holdout  a disjoint final-check pool.  It is listed for a later fetch and is
             intentionally absent from the shipped sources.jsonl, so a suite
             built from this corpus cannot be tuned against it.

Every suite that uses this corpus freezes its own token ids from the same
``sources.jsonl``; changing the tokenizer or chat encoder never edits the
corpus, it produces different requests.
"""

NAME = 'ru-prose'

SOURCE_NOTE = 'Russian Wikipedia prose, frozen at the listed revision.'
LICENSE_NOTE = ('License: CC BY-SA; follow the article history and Wikipedia terms when '
                'redistributing excerpts. Medical and legal texts are performance inputs, '
                'not advice.')

NOTES = [
    'Sources are frozen Russian Wikipedia prose: page id, revision, URL and SHA-256 per article.',
    'The dev pool was used by earlier Maya tuning; a suite built on it is a baseline, not a blind holdout.',
    'The holdout article list here is intentionally not part of sources.jsonl.',
    'Medical and legal texts are performance inputs, not advice or quality references.',
]

# Separate articles in each split; broad domains intentionally overlap.  The
# warmup pool is distinct from the measurement pool so that a warmed cache never
# hides the cost of a measurement article.
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
# encourages reaching a TG limit; it does not authorise ignoring natural EOS.
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
