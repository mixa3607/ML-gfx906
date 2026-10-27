"""Export HTML history JSON or a detailed Markdown report."""

from datetime import datetime
from html import escape
import math
import re

from common import BENCH, atomic_json, atomic_text, locked_paths, run_name, source_snapshot, timestamp
from .validate import read_validation


def verdict_for(item, validation):
    if validation is None:
        return item["verdict"]
    return validation["answers"].get(item["id"], {}).get("verdict")


def history_export(result, validation=None):
    counts = {"ok": 0, "mid": 0, "bad": 0, "skip": 0}
    got = 0
    maximum = 0
    for item in result["answers"]:
        verdict = verdict_for(item, validation)
        counts[{None: "skip", 0: "bad", 0.5: "mid", 1: "ok"}[verdict]] += 1
        got += (verdict or 0) * item["level"]
        maximum += item["level"]
    date = datetime.fromisoformat((validation or result)["updatedAt"])
    row = {
        "id": (validation or result)["id"],
        "model": result["name"],
        "date": int(date.timestamp() * 1000),
        # Match JavaScript Math.round, not Python's round-to-even.
        "score": math.floor(got / maximum * 100 + 0.5),
        "done": len(result["answers"]) - counts["skip"],
        "total": len(result["answers"]),
        "tps": None,
        "note": (f"Correct: {counts['ok']}; partial: {counts['mid']}; "
                 f"incorrect: {counts['bad']}; Пропущено: {counts['skip']}."),
        "counts": counts,
    }
    return {"app": "neuro-arena-2.1", "exported": timestamp(), "hist": [row]}


def markdown_inline(text):
    text = escape(" ".join(str(text).split()), quote=False)
    return re.sub(r"([\\`*_\[\]|~#])", r"\\\1", text)


def markdown_block(text):
    # Model answers can contain their own fences or HTML. Preserve them as
    # literal text without allowing them to change the report's structure.
    longest = max((len(part) for part in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def judgement_note(item, validation):
    if validation is not None and item["id"] in validation["answers"]:
        return validation["answers"][item["id"]]["explanation"]
    if item["response"] is None:
        return "Ответ модели ещё не получен."
    if validation is None:
        return "Файл валидации не выбран; пояснение валидатора отсутствует."
    return "Оценка валидатора отсутствует."


def markdown_export(result, validation=None):
    summary = history_export(result, validation)["hist"][0]
    counts = summary["counts"]
    labels = {
        1: "Верно (1)", 0.5: "Частично (0.5)", 0: "Неверно (0)",
        None: "Не удалось выбрать оценку / нет оценки (null)",
    }
    lines = [
        f"# Нейро-Арена — {markdown_inline(result['name'])}", "",
        f"Модель: {markdown_inline(result['model'])}", "",
        f"**Баллы: {summary['score']}/100** · Верно: {counts['ok']} · "
        f"Частично: {counts['mid']} · Неверно: {counts['bad']} · Пропущено: {counts['skip']}", "",
    ]
    if validation is not None:
        lines.extend([
            f"Валидатор: {markdown_inline(validation['validator']['model'])}", "",
            "Оценки и пояснения ниже даны LLM-валидатором и могут содержать ошибки.", "",
        ])
    lines.extend(["## Неуспешные ответы", ""])
    indexed = list(enumerate(result["answers"], 1))

    def append_index(items):
        if not items:
            lines.extend(["Нет.", ""])
            return
        lines.extend(["| Вопрос | Категория | Пояснение |", "| --- | --- | --- |"])
        for index, item in items:
            preview = " ".join(item["question"].split())
            if len(preview) > 120:
                preview = preview[:117] + "..."
            link = f"[{markdown_inline(item['id'])}](#question-{index})"
            lines.append(f"| {link} — {markdown_inline(preview)} | {markdown_inline(item['subject'])} "
                         f"| {markdown_inline(judgement_note(item, validation))} |")
        lines.append("")

    for verdict in (0, 0.5, None):
        items = [(index, item) for index, item in indexed if verdict_for(item, validation) == verdict]
        lines.extend([f"### {labels[verdict]} — {len(items)}", ""])
        append_index(items)

    if validation is not None:
        disputed = [(index, item) for index, item in indexed
                    if validation["answers"].get(item["id"], {}).get("referenceStatus") in ("disputed", "uncertain")]
        if disputed:
            lines.extend(["## Эталоны, требующие проверки", ""])
            append_index(disputed)

    lines.extend(["## Все вопросы по категориям", ""])
    subjects = {}
    for index, item in indexed:
        subjects.setdefault(item["subject"], []).append((index, item))
    reference_labels = {
        "accepted": "Принят (accepted)", "disputed": "Оспаривается (disputed)",
        "uncertain": "Не удалось проверить (uncertain)",
    }
    for subject, items in subjects.items():
        lines.extend([f"### {markdown_inline(subject)}", ""])
        for index, item in items:
            verdict = verdict_for(item, validation)
            lines.extend([
                f'<a id="question-{index}"></a>', "",
                f"#### {markdown_inline(item['id'])} — {labels[verdict]}", "",
                f"Уровень: {item['level']}", "",
                "**Вопрос**", "", markdown_block(item["question"]), "",
                "**Ответ модели**", "",
                markdown_block(item["answer"]) if item["answer"] is not None else "Ответ отсутствует.", "",
                "**Эталонный ответ**", "", markdown_block(item["reference"]), "",
            ])
            if item["explanation"]:
                lines.extend(["**Пояснение к эталону**", "", markdown_block(item["explanation"]), ""])
            lines.extend(["**Пояснение валидатора**", "", markdown_block(judgement_note(item, validation)), ""])
            judgement = validation["answers"].get(item["id"]) if validation is not None else None
            if judgement is not None:
                lines.extend([f"**Статус эталона:** {reference_labels[judgement['referenceStatus']]}", ""])
                if judgement["correctedAnswer"] is not None:
                    lines.extend(["**Предлагаемый эталон (correctedAnswer)**", "",
                                  markdown_block(judgement["correctedAnswer"]), ""])
    return "\n".join(lines)


def run(args):
    path = args.answers.resolve()
    protected = {BENCH.resolve()}
    if path in protected:
        raise ValueError("Answers path must not overwrite the config or source HTML")
    validation_path = args.validation.resolve() if args.validation else None
    if validation_path in protected | {path}:
        raise ValueError("Validation path must not overwrite the answers, config or source HTML")
    suffix = ".md" if args.format == "markdown" else ".import.json"
    output = (args.output or path.with_name(run_name(path) + suffix)).resolve()
    if output in protected | {path, validation_path}:
        raise ValueError("Export path must not overwrite the answers, validation or source HTML")
    inputs = [path] + ([validation_path] if validation_path else [])
    with locked_paths(*inputs):
        result, source_hash = source_snapshot(path)
        validation = read_validation(validation_path, result, source_hash) if validation_path else None
        if args.format == "markdown":
            atomic_text(output, markdown_export(result, validation))
        else:
            atomic_json(output, history_export(result, validation))
    print(f"Exported: {output}")
