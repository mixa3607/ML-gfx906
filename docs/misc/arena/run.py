#!/usr/bin/env python3
"""Collect, independently judge, and export Neuro-Arena answers."""

import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from html.parser import HTMLParser
from http.client import HTTPException
import json
import math
import os
from pathlib import Path
import re
import signal
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import uuid


BENCH = Path(__file__).with_name("Bench.html")
QUESTION_FIELDS = ("id", "subject", "level", "question", "reference", "explanation")
CONFIG_FIELDS = ("baseUrl", "model", "systemPrompt", "chatTemplateKwargs")
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


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "pre":
            self.parts.append("\n\n")
        elif tag == "br":
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(html):
    parser = PlainText()
    parser.feed(html)
    parser.close()
    return "".join(parser.parts).strip()


def extract_questions(path):
    source = path.read_text(encoding="utf-8")
    match = re.search(r"\bconst\s+DATA\s*=\s*", source)
    if not match:
        raise ValueError("Bench HTML does not contain const DATA")
    subjects, _ = json.JSONDecoder().raw_decode(source[match.end():])
    questions = []
    for subject in subjects:
        for index, question in enumerate(subject["q"]):
            questions.append({
                "id": f"{subject['id']}:{index}",
                "subject": subject["title"],
                "level": question["lvl"],
                "question": plain_text(question["q"]),
                "reference": plain_text(question["a"]),
                "explanation": question.get("n", ""),
            })
    if not questions or len({q["id"] for q in questions}) != len(questions):
        raise ValueError("Bench must contain questions with unique IDs")
    return questions


def load_config(path):
    try:
        import yaml
    except ImportError:
        raise ValueError("Install PyYAML: python3 -m pip install -r requirements.txt") from None
    try:
        with path.open(encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
    except yaml.YAMLError:
        # Parser messages may include lines containing authorization headers.
        raise ValueError("Invalid YAML config") from None
    if not isinstance(config, dict):
        raise ValueError("Config must be a YAML mapping")
    if "result" in config:
        raise ValueError("Remove result from the model config; use --answers and --validation instead")
    for key in ("baseUrl", "model"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"Config {key} must be a nonempty string")
    config["baseUrl"] = config["baseUrl"].rstrip("/")
    url = urlsplit(config["baseUrl"])
    if (url.scheme not in ("http", "https") or not url.hostname
            or url.username is not None or url.password is not None
            or url.query or url.fragment):
        raise ValueError("baseUrl must be an HTTP(S) URL without credentials, query or fragment")
    config.setdefault("headers", {})
    config.setdefault("chatTemplateKwargs", {})
    config.setdefault("systemPrompt", "")
    if not isinstance(config["systemPrompt"], str):
        raise ValueError("systemPrompt must be a string")
    headers = config["headers"]
    if not isinstance(headers, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
    ):
        raise ValueError("headers must map strings to strings")
    if not isinstance(config["chatTemplateKwargs"], dict):
        raise ValueError("chatTemplateKwargs must be a mapping")
    # Reject YAML-only values (dates, sets, non-string keys) before any requests.
    kwargs = config["chatTemplateKwargs"]
    encoded = json.dumps(kwargs, allow_nan=False)
    if json.loads(encoded) != kwargs:
        raise ValueError("chatTemplateKwargs must contain JSON-compatible values and string keys")
    return config


def run_name(path):
    return path.stem.removesuffix(".answers")


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def result_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("File is already in use by another command") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


@contextmanager
def locked_paths(*paths):
    with ExitStack() as stack:
        for path in sorted(set(paths)):
            stack.enter_context(result_lock(path))
        yield


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


def read_result(path, config=None, questions=None, source=None):
    result = json.loads(path.read_bytes() if source is None else source)
    if not isinstance(result, dict) or result.get("schemaVersion") != 1:
        raise ValueError("Unsupported result format")
    for key in ("id", "name", "createdAt", "updatedAt"):
        if not isinstance(result.get(key), str) or not result[key]:
            raise ValueError(f"Result must contain {key}")
    if config is not None:
        for key in CONFIG_FIELDS:
            if result.get(key) != config[key]:
                raise ValueError(f"Result {key} differs from config; use a different --answers file")
    answers = result.get("answers")
    if not isinstance(answers, list) or not answers:
        raise ValueError("Result must contain answers")
    ids = set()
    for item in answers:
        if not isinstance(item, dict) or not all(
            key in item for key in (*QUESTION_FIELDS, "verdict", "response", "answer")
        ):
            raise ValueError("Invalid question in result")
        if not isinstance(item["id"], str) or item["id"] in ids:
            raise ValueError("Invalid or duplicate question ID in result")
        ids.add(item["id"])
        level = item["level"]
        if type(level) is not int or level <= 0:
            raise ValueError(f"Invalid level for {item['id']}")
        verdict = item.get("verdict")
        if verdict is not None and (type(verdict) not in (int, float) or verdict not in (0, 0.5, 1)):
            raise ValueError(f"Invalid verdict for {item['id']}; expected null, 0, 0.5 or 1")
        if item.get("response") is not None:
            response_message(item["response"])
            if not isinstance(item.get("answer"), str):
                raise ValueError(f"Invalid saved answer for {item['id']}")
    if questions is not None:
        saved = [{key: item[key] for key in QUESTION_FIELDS} for item in answers]
        if saved != questions:
            raise ValueError("Bench questions differ from saved result; use a different --answers file")
    return result


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward configured authorization headers to a redirect target.
        return None


def response_message(response):
    try:
        message = response["choices"][0]["message"]
        if not isinstance(message, dict):
            raise ValueError
        content = message.get("content")
        if content is not None and not isinstance(content, str):
            raise ValueError
        if content is None and not any(
            isinstance(message.get(key), str)
            for key in ("reasoning_content", "reasoning", "refusal")
        ):
            raise ValueError
        return message
    except (KeyError, IndexError, TypeError, ValueError):
        raise ValueError("API response has no valid choices[0].message") from None


def chat_completion(config, question, timeout, response_format=None):
    messages = []
    if config["systemPrompt"]:
        messages.append({"role": "system", "content": config["systemPrompt"]})
    messages.append({"role": "user", "content": question})
    body = {
        "model": config["model"],
        "messages": messages,
        "chat_template_kwargs": config["chatTemplateKwargs"],
        "stream": False,
    }
    if response_format is not None:
        body["response_format"] = response_format
    headers = {"Content-Type": "application/json", **config["headers"]}
    request = Request(
        config["baseUrl"] + "/chat/completions",
        data=json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8"),
        headers=headers, method="POST",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            data = json.load(response)
    except HTTPError as error:
        code = error.code
        error.close()
        raise ValueError(f"API returned HTTP {code}; redirects are not followed") from None
    except URLError as error:
        raise ValueError(f"API connection failed: {error.reason}") from None
    response_message(data)
    return data


@contextmanager
def request_progress(done, total, item):
    stopped = threading.Event()
    started = time.monotonic()
    terminal = sys.stderr.isatty()

    def report():
        text = (f"[{done}/{total} {done / total:.0%}] {item['id']} "
                f"({item['subject']}) | waiting {time.monotonic() - started:.0f}s")
        print(("\r" if terminal else "") + text, end="" if terminal else "\n",
              file=sys.stderr, flush=True)

    def heartbeat():
        while not stopped.wait(1 if terminal else 30):
            report()

    report()
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join()
        if terminal:
            print(file=sys.stderr, flush=True)


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


def source_snapshot(path):
    source = path.read_bytes()
    return read_result(path, source=source), hashlib.sha256(source).hexdigest()


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


def positive_timeout(value):
    timeout = float(value)
    if not math.isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("timeout must be a finite positive number")
    return timeout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    examine_parser = commands.add_parser("examine", help="collect or resume model answers")
    examine_parser.add_argument("--bench", type=Path, default=BENCH, help="source HTML")
    validate_parser = commands.add_parser("validate", help="judge answers into a separate resumable file")
    export_parser = commands.add_parser("export", help="export an importable HTML history entry")
    export_parser.add_argument("--output", type=Path, help="default: <answers name>.import.json")
    for command in (examine_parser, validate_parser, export_parser):
        command.add_argument("--answers", type=Path, required=True, help="exam answers JSON path")
    for command in (examine_parser, validate_parser):
        command.add_argument("--model", type=Path, required=True, help="model YAML config")
        command.add_argument("--timeout", type=positive_timeout, default=3600,
                             help="per-request socket timeout in seconds (default: 3600)")
    validate_parser.add_argument("--validation", type=Path, required=True, help="judgements JSON path")
    export_parser.add_argument("--validation", type=Path, help="optional judgements JSON path")
    args = parser.parse_args(argv)
    try:
        path = args.answers.resolve()
        protected = {BENCH.resolve()}
        if args.mode != "export":
            config_path = args.model.resolve()
            protected.add(config_path)
            config = load_config(config_path)
        if args.mode == "examine":
            protected.add(args.bench.resolve())
        if path in protected:
            raise ValueError("Answers path must not overwrite the config or source HTML")
        if args.mode == "examine":
            examine(config, path, args.bench, args.timeout)
        else:
            validation_path = args.validation.resolve() if args.validation else None
            if validation_path in protected | {path}:
                raise ValueError("Validation path must not overwrite the answers, config or source HTML")
            if args.mode == "validate":
                validate(config, path, validation_path, args.timeout)
            else:
                output = (args.output or path.with_name(run_name(path) + ".import.json")).resolve()
                if output in protected | {path, validation_path}:
                    raise ValueError("Export path must not overwrite the answers, validation or source HTML")
                inputs = [path] + ([validation_path] if validation_path else [])
                with locked_paths(*inputs):
                    result, source_hash = source_snapshot(path)
                    validation = (read_validation(validation_path, result, source_hash)
                                  if validation_path else None)
                    atomic_json(output, history_export(result, validation))
                print(f"Exported: {output}")
    except KeyboardInterrupt:
        print("Interrupted. Saved progress is safe; rerun the same command to resume.",
              file=sys.stderr)
        return 130
    except (OSError, HTTPException, ValueError, TypeError, KeyError) as error:
        print(f"Error: {error}\nSaved progress is safe; rerun the same command to resume.", file=sys.stderr)
        return 1
    return 0


def interrupted(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
