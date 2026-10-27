"""Collect model answers, resuming from saved responses."""

import sys
import time
import uuid

from common import (
    BENCH, CONFIG_FIELDS, atomic_json, chat_completion, extract_questions,
    load_config, read_result, request_progress, response_message, result_lock,
    run_name, timestamp,
)


def new_result(config, path, questions):
    return {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()),
        "name": run_name(path),
        **{key: config[key] for key in CONFIG_FIELDS},
        "createdAt": timestamp(),
        "updatedAt": timestamp(),
        "answers": [dict(
            question, verdict=None, answer=None, reasoning=None, usage=None,
            response=None, elapsedSeconds=None, answeredAt=None,
        ) for question in questions],
    }


def examine(config, path, bench, timeout):
    questions = extract_questions(bench)
    with result_lock(path):
        if path.exists():
            result = read_result(path, config, questions)
        else:
            result = new_result(config, path, questions)
            atomic_json(path, result)
        answers = result["answers"]
        total = len(answers)
        done = sum(item["response"] is not None for item in answers)
        print(f"[{done}/{total}] Results: {path}", file=sys.stderr, flush=True)
        for item in answers:
            if item["response"] is not None:
                continue
            with request_progress(done, total, item):
                started = time.monotonic()
                response = chat_completion(config, item["question"], timeout)
                elapsed = time.monotonic() - started
            message = response_message(response)
            item.update(
                answer=message.get("content") or "",
                reasoning=message.get("reasoning_content", message.get("reasoning")),
                usage=response.get("usage"), response=response,
                elapsedSeconds=round(elapsed, 3), answeredAt=timestamp(),
            )
            result["updatedAt"] = timestamp()
            atomic_json(path, result)
            done += 1
            print(f"[{done}/{total} {done / total:.0%}] Saved {item['id']} ({elapsed:.1f}s)",
                  file=sys.stderr, flush=True)
        return result


def run(args):
    config_path = args.model.resolve()
    config = load_config(config_path)
    path = args.answers.resolve()
    if path in {config_path, BENCH.resolve(), args.bench.resolve()}:
        raise ValueError("Answers path must not overwrite the config or source HTML")
    examine(config, path, args.bench, args.timeout)
