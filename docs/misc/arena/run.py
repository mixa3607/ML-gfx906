#!/usr/bin/env python3
"""Collect Neuro-Arena answers and export its browser history format."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
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
    for key in ("baseUrl", "model", "result"):
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


def result_path(config, config_path):
    name = config["result"]
    if not name.endswith(".json"):
        name += ".json"
    return (config_path.parent / name).resolve()


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
            raise ValueError("Result is already in use by another examine/export process") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def new_result(config, path, questions):
    return {
        "schemaVersion": 1,
        "id": str(uuid.uuid4()),
        "name": path.stem,
        **{key: config[key] for key in CONFIG_FIELDS},
        "createdAt": timestamp(),
        "updatedAt": timestamp(),
        "answers": [dict(
            question, verdict=None, answer=None, reasoning=None, usage=None,
            response=None, elapsedSeconds=None, answeredAt=None,
        ) for question in questions],
    }


def read_result(path, config, questions=None):
    with path.open(encoding="utf-8") as stream:
        result = json.load(stream)
    if not isinstance(result, dict) or result.get("schemaVersion") != 1:
        raise ValueError("Unsupported result format")
    for key in CONFIG_FIELDS:
        if result.get(key) != config[key]:
            raise ValueError(f"Result {key} differs from config; use a different result name")
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
            raise ValueError("Bench questions differ from saved result; use a different result name")
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


def chat_completion(config, question, timeout):
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


def history_export(result):
    counts = {"ok": 0, "mid": 0, "bad": 0, "skip": 0}
    got = 0
    maximum = 0
    for item in result["answers"]:
        verdict = item["verdict"]
        counts[{None: "skip", 0: "bad", 0.5: "mid", 1: "ok"}[verdict]] += 1
        got += (verdict or 0) * item["level"]
        maximum += item["level"]
    date = datetime.fromisoformat(result["updatedAt"])
    row = {
        "id": result["id"],
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
    examine_parser.add_argument("config", type=Path, help="model YAML config")
    examine_parser.add_argument("--bench", type=Path, default=BENCH, help="source HTML")
    examine_parser.add_argument("--timeout", type=positive_timeout, default=3600,
                                help="per-request socket timeout in seconds (default: 3600)")
    validate_parser = commands.add_parser("valudate", help="placeholder for future LLM validation")
    validate_parser.add_argument("config", type=Path, help="model YAML config")
    validate_parser.add_argument("--validator", type=Path, default=Path("validator.yaml"),
                                 help="future validator config (not read yet)")
    export_parser = commands.add_parser("export", help="export an importable HTML history entry")
    export_parser.add_argument("config", type=Path, help="model YAML config")
    export_parser.add_argument("--output", type=Path, help="default: <result>.import.json")
    args = parser.parse_args(argv)
    if args.mode == "valudate":
        print("valudate is not implemented; no files changed and no requests sent.", file=sys.stderr)
        return 2
    try:
        config_path = args.config.resolve()
        config = load_config(config_path)
        path = result_path(config, config_path)
        protected = {config_path, BENCH.resolve()}
        if args.mode == "examine":
            protected.add(args.bench.resolve())
        if path in protected:
            raise ValueError("Result path must not overwrite the config or source HTML")
        if args.mode == "examine":
            examine(config, path, args.bench, args.timeout)
        else:
            output = (args.output or path.with_name(path.stem + ".import.json")).resolve()
            if output in protected | {path}:
                raise ValueError("Export path must not overwrite the result, config or source HTML")
            with result_lock(path):
                result = read_result(path, config)
                atomic_json(output, history_export(result))
            print(f"Exported: {output}")
    except KeyboardInterrupt:
        print("Interrupted. Saved answers are safe; rerun examine with the same config to resume.",
              file=sys.stderr)
        return 130
    except (OSError, HTTPException, ValueError, TypeError, KeyError) as error:
        print(f"Error: {error}\nSaved answers are unchanged; rerun examine to resume.", file=sys.stderr)
        return 1
    return 0


def interrupted(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
