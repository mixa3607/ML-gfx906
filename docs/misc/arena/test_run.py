from contextlib import contextmanager, redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import yaml

import run


def completion(answer="Ответ"):
    return {
        "id": "chatcmpl-test",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": answer, "reasoning_content": "Мысль"},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
        "server_field": "preserved",
    }


@contextmanager
def mock_api(responses):
    requests = []
    queue = list(responses)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append({"path": self.path, "headers": self.headers, "body": json.loads(body)})
            status, response = queue.pop(0) if queue else (500, {"error": "Unexpected request"})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            if status == 307:
                self.send_header("Location", "/redirected")
            self.end_headers()
            self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

        def log_message(self, format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bench = self.root / "Bench.html"
        self.config_path = self.root / "model.yaml"
        self.path = self.root / "model-rea95.json"
        self.config = {
            "baseUrl": "http://127.0.0.1:1/v1",
            "model": "ds41f",
            "systemPrompt": "Отвечай точно.",
            "headers": {"Authorization": "Bearer secret-test-token", "X-Test": "hello"},
            "chatTemplateKwargs": {"reasoning_effort": 95},
            "result": "model-rea95",
        }
        self.subjects = [{
            "id": "test", "title": "Тест", "q": [
                {"lvl": 6, "q": "Вопрос?<pre>x &lt; 2\n  return x</pre>",
                 "a": "Секретный эталон", "n": "Секретное пояснение"},
                {"lvl": 2, "q": "Второй вопрос?", "a": "42"},
            ],
        }]
        self.write_bench()
        self.write_config()

    def write_bench(self):
        self.bench.write_text("<script>const DATA = " + json.dumps(
            self.subjects, ensure_ascii=False,
        ) + "; throw new Error('must not execute');</script>", encoding="utf-8")

    def write_config(self):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True), encoding="utf-8")

    def invoke(self, *args):
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            code = run.main(list(map(str, args)))
        return code, output.getvalue()

    def examine(self):
        return self.invoke("examine", self.config_path, "--bench", self.bench, "--timeout", "2")

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def initialize(self):
        result = run.new_result(self.config, self.path, run.extract_questions(self.bench))
        run.atomic_json(self.path, result)
        return result

    def test_real_bench_has_100_unique_questions(self):
        questions = run.extract_questions(run.BENCH)
        self.assertEqual(len(questions), 100)
        self.assertEqual(len({q["subject"] for q in questions}), 20)
        self.assertEqual(len({q["id"] for q in questions}), 100)
        self.assertEqual(questions[0]["id"], "math:0")
        self.assertEqual(questions[0]["reference"], "153")

    def test_extract_json_without_executing_js_and_preserve_code(self):
        questions = run.extract_questions(self.bench)
        self.assertEqual(questions[0]["question"], "Вопрос?\n\nx < 2\n  return x")
        self.assertEqual(questions[1]["explanation"], "")
        self.assertEqual(run.plain_text("<b>A</b><br>B &amp; C"), "A\nB & C")

    def test_initial_result_contains_all_null_verdicts(self):
        result = self.initialize()
        self.assertEqual(len(result["answers"]), 2)
        self.assertTrue(all(item["verdict"] is None for item in result["answers"]))
        self.assertTrue(all(item["response"] is None for item in result["answers"]))
        self.assertNotIn("headers", result)

    def test_examine_http_payload_output_and_idempotent_resume(self):
        with mock_api([(200, completion("Первый")), (200, completion("Второй"))]) as (url, requests):
            self.config["baseUrl"] = url + "/"
            self.write_config()
            code, log = self.examine()
            self.assertEqual(code, 0, log)
            self.assertIn("[2/2 100%]", log)
            self.assertEqual(len(requests), 2)
            for request in requests:
                self.assertEqual(request["path"], "/v1/chat/completions")
                self.assertEqual(request["headers"]["Authorization"], "Bearer secret-test-token")
                self.assertEqual(request["headers"]["X-Test"], "hello")
                self.assertEqual(request["body"]["chat_template_kwargs"], {"reasoning_effort": 95})
                self.assertFalse(request["body"]["stream"])
                self.assertEqual(request["body"]["model"], "ds41f")
                self.assertEqual(len(request["body"]["messages"]), 2)
                self.assertEqual(request["body"]["messages"][0], {
                    "role": "system", "content": "Отвечай точно.",
                })
                self.assertNotIn("Секрет", json.dumps(request["body"], ensure_ascii=False))
            result = self.read()
            self.assertEqual(result["answers"][0]["answer"], "Первый")
            self.assertEqual(result["answers"][0]["reasoning"], "Мысль")
            self.assertEqual(result["answers"][1]["response"], completion("Второй"))
            self.assertEqual(result["answers"][0]["usage"]["completion_tokens"], 20)
            self.assertIsNotNone(result["answers"][0]["answeredAt"])
            self.assertGreaterEqual(result["answers"][0]["elapsedSeconds"], 0)
            self.assertNotIn("secret-test-token", self.path.read_text())
            self.assertNotIn("secret-test-token", log)
            # Token rotation is allowed; a completed run sends no requests.
            self.config["headers"]["Authorization"] = "Bearer rotated-token"
            self.write_config()
            before = self.path.read_bytes()
            self.assertEqual(self.examine()[0], 0)
            self.assertEqual(len(requests), 2)
            self.assertEqual(self.path.read_bytes(), before)

    def test_error_stops_and_resume_only_requests_unfinished(self):
        with mock_api([(200, completion()), (503, {"error": "unavailable"}),
                       (200, completion("Повтор"))]) as (url, requests):
            self.config["baseUrl"] = url
            self.write_config()
            code, log = self.examine()
            self.assertEqual(code, 1)
            self.assertIn("HTTP 503", log)
            partial = self.read()
            self.assertIsNotNone(partial["answers"][0]["response"])
            self.assertIsNone(partial["answers"][1]["response"])
            partial["answers"][0]["verdict"] = 0.5
            run.atomic_json(self.path, partial)
            self.assertEqual(self.examine()[0], 0)
            self.assertEqual(len(requests), 3)
            self.assertEqual(requests[1]["body"], requests[2]["body"])
            self.assertEqual(self.read()["answers"][0]["verdict"], 0.5)

    def test_ctrl_c_preserves_checkpoint(self):
        with patch.object(run, "chat_completion", side_effect=[completion(), KeyboardInterrupt]):
            code, log = self.examine()
        self.assertEqual(code, 130)
        self.assertIn("Interrupted", log)
        result = self.read()
        self.assertIsNotNone(result["answers"][0]["response"])
        self.assertIsNone(result["answers"][1]["response"])

    def test_timeout_or_incomplete_http_preserves_checkpoint(self):
        for error in (TimeoutError("timed out"), IncompleteRead(b"partial", 100)):
            with self.subTest(error=type(error).__name__):
                with patch.object(run, "chat_completion", side_effect=error):
                    code, log = self.examine()
                self.assertEqual(code, 1)
                self.assertIn("Error:", log)
                self.assertNotIn("Traceback", log)
                self.assertTrue(all(a["response"] is None for a in self.read()["answers"]))

    def test_changed_parameters_refuse_resume_without_writes(self):
        self.initialize()
        before = self.path.read_bytes()
        for key, value in (("model", "other"), ("systemPrompt", "new"),
                           ("chatTemplateKwargs", {"reasoning_effort": 1}),
                           ("baseUrl", "http://127.0.0.1:2/v1")):
            with self.subTest(key=key):
                original = self.config[key]
                self.config[key] = value
                self.write_config()
                with patch.object(run, "chat_completion") as call:
                    code, log = self.examine()
                self.assertEqual(code, 1)
                self.assertIn(f"{key} differs", log)
                call.assert_not_called()
                self.assertEqual(before, self.path.read_bytes())
                self.config[key] = original

    def test_changed_questions_refuse_resume(self):
        self.initialize()
        before = self.path.read_bytes()
        self.subjects[0]["q"][0]["q"] = "Changed"
        self.write_bench()
        with patch.object(run, "chat_completion") as call:
            code, log = self.examine()
        self.assertEqual(code, 1)
        self.assertIn("questions differ", log)
        call.assert_not_called()
        self.assertEqual(before, self.path.read_bytes())

    def test_redirect_is_not_followed(self):
        with mock_api([(307, {})]) as (url, requests):
            self.config["baseUrl"] = url
            self.write_config()
            code, log = self.examine()
            self.assertEqual(code, 1)
            self.assertIn("HTTP 307", log)
            self.assertEqual(len(requests), 1)
        self.assertTrue(all(a["response"] is None for a in self.read()["answers"]))

    def test_invalid_api_response_not_marked_completed(self):
        with mock_api([(200, {"choices": []})]) as (url, _):
            self.config["baseUrl"] = url
            self.write_config()
            code, log = self.examine()
        self.assertEqual(code, 1)
        self.assertIn("no valid", log)
        self.assertTrue(all(a["response"] is None for a in self.read()["answers"]))

    def test_empty_system_prompt_and_optional_defaults(self):
        self.config.pop("systemPrompt")
        self.config.pop("headers")
        self.config.pop("chatTemplateKwargs")
        with mock_api([(200, completion()), (200, completion())]) as (url, requests):
            self.config["baseUrl"] = url
            self.write_config()
            self.assertEqual(self.examine()[0], 0)
            self.assertEqual(requests[0]["body"]["messages"], [{
                "role": "user", "content": "Вопрос?\n\nx < 2\n  return x",
            }])
            self.assertEqual(requests[0]["body"]["chat_template_kwargs"], {})

    def test_atomic_replace_failure_preserves_previous_file(self):
        self.initialize()
        before = self.path.read_bytes()
        with patch.object(run.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                run.atomic_json(self.path, {"new": "data"})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_concurrent_result_lock_is_rejected(self):
        with run.result_lock(self.path):
            code, log = self.examine()
        self.assertEqual(code, 1)
        self.assertIn("already in use", log)
        self.assertFalse(self.path.exists())

    def test_export_all_null_as_skipped_without_api_calls(self):
        result = self.initialize()
        before = self.path.read_bytes()
        with patch.object(run, "chat_completion") as call:
            code, log = self.invoke("export", self.config_path)
        self.assertEqual(code, 0, log)
        call.assert_not_called()
        exported = json.loads((self.root / "model-rea95.import.json").read_text())
        self.assertEqual(exported["app"], "neuro-arena-2.1")
        row = exported["hist"][0]
        self.assertEqual(row["model"], "model-rea95")
        self.assertEqual(row["id"], result["id"])
        self.assertEqual(row["score"], 0)
        self.assertEqual(row["done"], 0)
        self.assertEqual(row["total"], 2)
        self.assertEqual(row["counts"], {"ok": 0, "mid": 0, "bad": 0, "skip": 2})
        self.assertIn("Пропущено: 2", row["note"])
        self.assertIsNone(row["tps"])
        self.assertIsInstance(row["date"], int)
        self.assertEqual(before, self.path.read_bytes())

    def test_export_scoring_skip_denominator_and_js_rounding(self):
        result = self.initialize()
        result["answers"][0]["verdict"] = 0.5
        row = run.history_export(result)["hist"][0]
        self.assertEqual(row["score"], 38)  # 3/8 = 37.5, rounds up.
        self.assertEqual(row["done"], 1)
        self.assertEqual(row["counts"]["skip"], 1)
        result["answers"][0]["verdict"] = 1
        result["answers"][1]["verdict"] = 0
        row = run.history_export(result)["hist"][0]
        self.assertEqual(row["score"], 75)
        self.assertEqual(row["done"], 2)
        self.assertEqual(row["counts"], {"ok": 1, "mid": 0, "bad": 1, "skip": 0})

    def test_export_rounds_half_up_instead_of_to_even(self):
        result = self.initialize()
        result["answers"][0].update(level=1, verdict=0.5)
        result["answers"][1]["level"] = 3
        self.assertEqual(run.history_export(result)["hist"][0]["score"], 13)

    def test_invalid_verdict_is_rejected(self):
        result = self.initialize()
        result["answers"][0]["verdict"] = "null"
        run.atomic_json(self.path, result)
        code, log = self.invoke("export", self.config_path)
        self.assertEqual(code, 1)
        self.assertIn("Invalid verdict", log)

    def test_valudate_stub_does_not_read_or_change_files(self):
        code, log = self.invoke("valudate", self.root / "missing.yaml")
        self.assertEqual(code, 2)
        self.assertIn("not implemented", log)
        self.assertFalse(self.path.exists())

    def test_result_path_relative_to_config_and_suffix(self):
        self.assertEqual(run.result_path(self.config, self.config_path), self.path)
        self.config["result"] = "sub/model.json"
        self.assertEqual(run.result_path(self.config, self.config_path), self.root / "sub/model.json")
        self.config["result"] = "model-1.5"
        self.assertEqual(run.result_path(self.config, self.config_path), self.root / "model-1.5.json")

    def test_invalid_yaml_has_no_traceback_or_credentials(self):
        self.config_path.write_text("headers: [Bearer secret-test-token\n")
        code, log = self.examine()
        self.assertEqual(code, 1)
        self.assertIn("Invalid YAML", log)
        self.assertNotIn("Traceback", log)
        self.assertNotIn("secret-test-token", log)

    def test_result_cannot_overwrite_source_html(self):
        source = self.root / "source.json"
        source.write_bytes(self.bench.read_bytes())
        before = source.read_bytes()
        self.config["result"] = str(source)
        self.write_config()
        code, log = self.invoke("examine", self.config_path, "--bench", source)
        self.assertEqual(code, 1)
        self.assertIn("must not overwrite", log)
        self.assertEqual(source.read_bytes(), before)

    def test_export_cannot_overwrite_result(self):
        self.initialize()
        before = self.path.read_bytes()
        code, log = self.invoke("export", self.config_path, "--output", self.path)
        self.assertEqual(code, 1)
        self.assertIn("must not overwrite", log)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
