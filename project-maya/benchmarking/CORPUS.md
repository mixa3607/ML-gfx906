# Warmup and measurement inputs

Minimal input recipe retained from the serial warm-cache experiments. It is
independent of engine launch settings. The original frozen source texts and
tokenized case files are **not included** here; the lists below are a recipe,
not a byte-identical replacement for those files.

## Source material

Use real Russian Wikipedia prose. Acquire each article once, freeze the text,
and retain its page ID, revision URL, text SHA-256 and attribution/license data.
Revision URLs have the form `https://ru.wikipedia.org/w/index.php?oldid=REVISION`.
Follow the article's license and attribution terms when redistributing excerpts.
Do not refetch current article revisions separately for each engine.

Warmup and measurement use **different articles**, while broad topics may
overlap. Resolve redirects and check page IDs so aliases cannot leak an article
across splits. Medical/legal texts are performance inputs, not advice or quality
references.

### Warmup pool: 12 articles

1. Фотосинтез
2. Великий шёлковый путь
3. Тепловой насос
4. Шахматы
5. Инфляция
6. Народная музыка
7. Гражданское право
8. Сон
9. Почва
10. Реляционная база данных
11. Северный Ледовитый океан
12. Керамика

### Measurement pool: 24 articles

1. Вулкан
2. Книгопечатание
3. Электрический двигатель
4. Волейбол
5. Страхование
6. Импрессионизм
7. Авторское право
8. Иммунная система
9. Пчеловодство
10. Операционная система
11. Озеро Байкал
12. Бетон
13. Спектроскопия
14. Ганзейский союз
15. Транзистор
16. Фигурное катание
17. Логистика
18. Русская литература
19. Трудовое право
20. Пищеварение
21. Лесоводство
22. Компилятор
23. Кавказ
24. Стекло

The pool is larger than six requests so longer prompts can consume additional
unique prose without repeating paragraphs. For a final post-tuning check,
freeze another disjoint article pool rather than reusing the measurement pool.

## Task templates

Cycle through these six Russian tasks in order, independently in each split.
The requested answer length encourages reaching the TG256 generation limit;
it does not authorize ignoring natural EOS.

1. Объясни содержание человеку без специальной подготовки. Разверни ответ: не менее 500 слов, с примерами и оговорками.
2. Подготовь подробную аналитическую записку: основные положения, причинные связи, ограничения и открытые вопросы. Не менее 500 слов.
3. Составь развёрнутый учебный диалог: собеседник сомневается, эксперт отвечает и исправляет заблуждения. Не менее 500 слов.
4. Напиши подробный план выступления с пояснениями, примерами и ответами на возможные вопросы аудитории. Не менее 500 слов.
5. Преобразуй материал в ясную статью для неспециалиста. Разделяй установленные факты и предположения; не менее 500 слов.
6. Разбери материал критически: терминология, аргументы, возможные ошибки интерпретации и вопросы для проверки. Не менее 500 слов.

## Assemble and freeze the cases

1. Shuffle each source pool with a recorded seed; `20261024` was the short-suite
   seed. Save the resulting source order as well: a seed alone does not specify
   the shuffle implementation or the source revisions.
2. Create 12 warmup requests at **PP2048**, then six measurement requests at
   **PP2048, PP4096, PP8192, PP2048, PP4096, PP8192**. Rotate the lead article
   and task. Consume unused source passages, continuing into another article
   where needed; never reuse a source byte range within the suite.
3. Use a consistent user-message layout, then apply the target model's chat
   template and tokenizer:

   ```text
   <lead article title>. <task>

   Материалы:
   <article title>
   <unused source passage>

   <next article title, if needed>
   <unused source passage>
   ```

4. Fit the **complete tokenized input** to the target PP by cutting only source
   material, not the task, system text or generation header. This is input
   preparation, not permission for the engine to truncate a submitted request.
   If there is not enough unique text, extend and refreeze the source pool; do
   not pad it with repeated paragraphs. Check every final token count.
5. Save each case's ID, phase (`warmup` or `measurement`), target PP, rendered
   text, token IDs, input hash, source revision/hash and consumed byte ranges.
   Verify that prompts are distinct and source passages do not overlap. Freeze
   the ordered case file and its SHA-256 **before measuring any candidate**.

Use exactly the same cases for engine/configuration comparisons with the same
model/tokenizer. Across different models, exact PP may require different source
cut points; preserve topic/task pairing and disclose that the tokenized inputs
are not identical. These prose samples do not represent all Russian chat, slang,
code or document-processing traffic.
