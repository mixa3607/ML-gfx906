"""Judge model answers into a separate, source-bound validation file."""

import hashlib
import json
import sys
import time
import uuid

from common import (
    BENCH, CONFIG_FIELDS, atomic_json, chat_completion, load_config, locked_paths,
    request_progress, response_message, source_snapshot, timestamp,
)


JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": ["number", "null"], "enum": [0, 0.5, 1, None]},
        "referenceStatus": {"type": "string", "enum": ["accepted", "disputed", "uncertain"]},
        "correctedAnswer": {"type": ["string", "null"]},
        "explanation": {"type": "string"},
    },
    "required": ["verdict", "referenceStatus", "correctedAnswer", "explanation"],
}
JUDGE_FORMAT = {
    "type": "json_schema",
    "json_schema": {"name": "benchmark_verdict", "strict": True, "schema": JUDGE_SCHEMA},
}


def judge_schema_validator():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        raise ValueError("Install jsonschema: python3 -m pip install -r requirements.txt") from None
    return Draft202012Validator(JUDGE_SCHEMA)


def check_judgement(value):
    if next(judge_schema_validator().iter_errors(value), None) is not None:
        raise ValueError("Judge output does not match the required JSON Schema")
    corrected = value["correctedAnswer"]
    if value["referenceStatus"] == "disputed":
        if not isinstance(corrected, str) or not corrected.strip():
            raise ValueError("A disputed reference requires a nonempty correctedAnswer")
    elif corrected is not None:
        raise ValueError("correctedAnswer must be null unless referenceStatus is disputed")
    if not value["explanation"].strip():
        raise ValueError("Judge explanation must not be empty")
    return value


def unique_keys(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Judge JSON contains duplicate keys")
        value[key] = item
    return value


def parse_judgement(response):
    message = response_message(response)
    if response["choices"][0].get("finish_reason") != "stop":
        raise ValueError("Judge response did not finish normally; judgement was not saved")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("Judge response has no JSON content")
    try:
        value = json.loads(content, object_pairs_hook=unique_keys)
    except json.JSONDecodeError:
        raise ValueError("Judge response is not a JSON document") from None
    return check_judgement(value)


def new_validation(config, result, source_hash):
    return {
        "schemaVersion": 1,
        "kind": "arena-validation",
        "id": str(uuid.uuid4()),
        "sourceRunId": result["id"],
        "sourceSha256": source_hash,
        "validator": {key: config[key] for key in CONFIG_FIELDS},
        "responseFormat": JUDGE_FORMAT,
        "createdAt": timestamp(),
        "updatedAt": timestamp(),
        "answers": {},
    }


def read_validation(path, result, source_hash, config=None):
    validation = json.loads(path.read_bytes())
    if (not isinstance(validation, dict) or validation.get("schemaVersion") != 1
            or validation.get("kind") != "arena-validation"):
        raise ValueError("Unsupported validation format")
    if validation.get("sourceRunId") != result["id"] or validation.get("sourceSha256") != source_hash:
        raise ValueError("Validation source differs from --answers; use a different --validation file")
    if validation.get("responseFormat") != JUDGE_FORMAT:
        raise ValueError("Validation schema differs; use a different --validation file")
    if config is not None:
        expected = {key: config[key] for key in CONFIG_FIELDS}
        if validation.get("validator") != expected:
            raise ValueError("Validator config differs; use a different --validation file")
    for key in ("id", "createdAt", "updatedAt"):
        if not isinstance(validation.get(key), str) or not validation[key]:
            raise ValueError(f"Validation must contain {key}")
    judgements = validation.get("answers")
    if not isinstance(judgements, dict):
        raise ValueError("Validation must contain an answers mapping")
    eligible = {item["id"] for item in result["answers"] if item["response"] is not None}
    for key, item in judgements.items():
        if key not in eligible or not isinstance(item, dict):
            raise ValueError("Validation contains an unknown or unanswered question")
        if not all(field in item for field in (*JUDGE_SCHEMA["required"], "validatedAt", "elapsedSeconds")):
            raise ValueError("Saved judgement is missing required fields")
        check_judgement({field: item[field] for field in JUDGE_SCHEMA["required"]})
        if not isinstance(item.get("response"), dict):
            raise ValueError("Saved judgement has no API response")
        response_message(item["response"])
    return validation


def validate(config, answers_path, validation_path, timeout):
    judge_schema_validator()
    with locked_paths(answers_path, validation_path):
        result, source_hash = source_snapshot(answers_path)
        if validation_path.exists():
            validation = read_validation(validation_path, result, source_hash, config)
        else:
            validation = new_validation(config, result, source_hash)
            atomic_json(validation_path, validation)
        eligible = [item for item in result["answers"] if item["response"] is not None]
        total = len(eligible)
        done = len(validation["answers"])
        print(f"[{done}/{total}] Validation: {validation_path}", file=sys.stderr, flush=True)
        for item in eligible:
            if item["id"] in validation["answers"]:
                continue
            content = json.dumps({
                "question": item["question"],
                "candidateAnswer": item["answer"],
                "referenceAnswer": item["reference"],
                "referenceExplanation": item["explanation"],
            }, ensure_ascii=False)
            with request_progress(done, total, item):
                started = time.monotonic()
                response = chat_completion(config, content, timeout, response_format=JUDGE_FORMAT)
                elapsed = time.monotonic() - started
            judgement = parse_judgement(response)
            if hashlib.sha256(answers_path.read_bytes()).hexdigest() != source_hash:
                raise ValueError("Answers changed during validation; judgement was not saved")
            validation["answers"][item["id"]] = {
                **judgement, "response": response,
                "elapsedSeconds": round(elapsed, 3), "validatedAt": timestamp(),
            }
            validation["updatedAt"] = timestamp()
            atomic_json(validation_path, validation)
            done += 1
            print(f"[{done}/{total} {done / total:.0%}] Judged {item['id']} "
                  f"(verdict={judgement['verdict']}, {elapsed:.1f}s)", file=sys.stderr, flush=True)
        return validation


def run(args):
    config_path = args.model.resolve()
    config = load_config(config_path)
    path = args.answers.resolve()
    protected = {config_path, BENCH.resolve()}
    if path in protected:
        raise ValueError("Answers path must not overwrite the config or source HTML")
    validation_path = args.validation.resolve()
    if validation_path in protected | {path}:
        raise ValueError("Validation path must not overwrite the answers, config or source HTML")
    validate(config, path, validation_path, args.timeout)
