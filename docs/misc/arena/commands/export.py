"""Export answer verdicts or selected judgements to the HTML history format."""

from datetime import datetime
import math

from common import BENCH, atomic_json, locked_paths, run_name, source_snapshot, timestamp
from .validate import read_validation


def history_export(result, validation=None):
    counts = {"ok": 0, "mid": 0, "bad": 0, "skip": 0}
    got = 0
    maximum = 0
    for item in result["answers"]:
        if validation is None:
            verdict = item["verdict"]
        else:
            verdict = validation["answers"].get(item["id"], {}).get("verdict")
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


def run(args):
    path = args.answers.resolve()
    protected = {BENCH.resolve()}
    if path in protected:
        raise ValueError("Answers path must not overwrite the config or source HTML")
    validation_path = args.validation.resolve() if args.validation else None
    if validation_path in protected | {path}:
        raise ValueError("Validation path must not overwrite the answers, config or source HTML")
    output = (args.output or path.with_name(run_name(path) + ".import.json")).resolve()
    if output in protected | {path, validation_path}:
        raise ValueError("Export path must not overwrite the answers, validation or source HTML")
    inputs = [path] + ([validation_path] if validation_path else [])
    with locked_paths(*inputs):
        result, source_hash = source_snapshot(path)
        validation = read_validation(validation_path, result, source_hash) if validation_path else None
        atomic_json(output, history_export(result, validation))
    print(f"Exported: {output}")
