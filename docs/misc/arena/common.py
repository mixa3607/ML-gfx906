"""Shared benchmark parsing, API access, progress and file handling."""

from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


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
    lock_path = path.with_name(path.name + ".lock")
    while True:
        with lock_path.open("a") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError("File is already in use by another command") from None
            try:
                # A previous owner may have unlinked this inode after we opened
                # it. Only enter while holding the inode still named by the path.
                if not lock_matches(lock_path, stream):
                    continue
                try:
                    yield
                finally:
                    # Unlink while still locked. Contenders with an old open
                    # descriptor must retry, rather than use an unlinked lock.
                    if lock_matches(lock_path, stream):
                        lock_path.unlink(missing_ok=True)
                return
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def lock_matches(path, stream):
    try:
        return os.path.samestat(path.stat(), os.fstat(stream.fileno()))
    except FileNotFoundError:
        return False


@contextmanager
def locked_paths(*paths):
    with ExitStack() as stack:
        for path in sorted(set(paths)):
            stack.enter_context(result_lock(path))
        yield


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


def source_snapshot(path):
    source = path.read_bytes()
    return read_result(path, source=source), hashlib.sha256(source).hexdigest()
