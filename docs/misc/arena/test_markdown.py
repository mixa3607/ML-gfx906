from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from commands import examine, export, validate
import common
import run
from test_run import completion, judge_completion, judgement


class MarkdownExportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "model.answers.json"
        self.validation_path = self.root / "model.validation.json"
        config = {
            "baseUrl": "http://127.0.0.1:1/v1", "model": "candidate-model",
            "systemPrompt": "Assistant", "chatTemplateKwargs": {},
        }
        questions = []
        for index, subject in enumerate(("Математика", "Физика", "Математика", "Физика",
                                         "Математика", "Физика", "Физика")):
            questions.append({
                "id": f"test:{index}", "subject": subject, "level": 6,
                "question": f"Question {index}?", "reference": f"Reference {index}",
                "explanation": f"Reference explanation {index}",
            })
        self.result = examine.new_result(config, self.path, questions)
        for index, item in enumerate(self.result["answers"]):
            if index != 5:
                item.update(answer=f"Candidate answer {index}", reasoning="PRIVATE CANDIDATE REASONING",
                            response=completion(f"Candidate answer {index}"))
        common.atomic_json(self.path, self.result)
        _, source_hash = common.source_snapshot(self.path)
        self.validation = validate.new_validation({**config, "model": "judge-model"}, self.result, source_hash)
        # Incorrect, correct with a disputed reference, partial, explicit null,
        # not yet judged, not yet answered, and another correct answer.
        for index, verdict, status, corrected in (
            (0, 0, "accepted", None),
            (1, 1, "disputed", "Proposed corrected reference"),
            (2, 0.5, "accepted", None),
            (3, None, "uncertain", None),
            (6, 1, "accepted", None),
        ):
            response = judge_completion(verdict, status, corrected)
            response["choices"][0]["message"]["reasoning_content"] = "PRIVATE JUDGE REASONING"
            self.validation["answers"][f"test:{index}"] = {
                **judgement(verdict, status, corrected), "response": response,
                "elapsedSeconds": 1, "validatedAt": common.timestamp(),
            }
        common.atomic_json(self.validation_path, self.validation)

    def tearDown(self):
        self.assertEqual(list(self.root.rglob("*.lock")), [])

    def invoke(self, *args):
        log = io.StringIO()
        with redirect_stdout(log), redirect_stderr(log):
            code = run.main(["export", "--answers", str(self.path), *map(str, args)])
        return code, log.getvalue()

    def report(self):
        return export.markdown_export(self.result, self.validation)

    def test_unsuccessful_index_comes_first_in_requested_order(self):
        report = self.report()
        overview, details = report.split("## Все вопросы по категориям", 1)
        failures = overview.split("## Эталоны, требующие проверки", 1)[0]
        self.assertLess(failures.index("### Неверно (0) — 1"), failures.index("### Частично (0.5) — 1"))
        self.assertLess(failures.index("### Частично (0.5) — 1"), failures.index("(null) — 3"))
        self.assertIn("[test:0](#question-1)", failures)
        self.assertIn("[test:2](#question-3)", failures)
        for index in (3, 4, 5):
            self.assertIn(f"[test:{index}](#question-{index + 1})", failures)
        for index in (1, 6):
            self.assertNotIn(f"[test:{index}]", failures)
        self.assertIn("Краткое обоснование оценки.", failures)
        self.assertIn("**Баллы: 36/100**", overview)
        self.assertIn("Верно: 2 · Частично: 1 · Неверно: 1 · Пропущено: 3", overview)
        self.assertIn("Candidate answer 6", details)

    def test_all_questions_grouped_by_subject_with_working_links(self):
        report = self.report()
        details = report.split("## Все вопросы по категориям", 1)[1]
        math, physics = details.split("### Физика", 1)
        self.assertIn("### Математика", math)
        self.assertEqual(re.findall(r"#### test:(\d+)", math), ["0", "2", "4"])
        self.assertEqual(re.findall(r"#### test:(\d+)", physics), ["1", "3", "5", "6"])
        anchors = re.findall(r'<a id="([^"]+)"></a>', report)
        self.assertEqual(len(anchors), 7)
        self.assertEqual(len(set(anchors)), 7)
        for target in re.findall(r"\]\(#([^\)]+)\)", report):
            self.assertIn(target, anchors)

    def test_full_details_include_judge_explanation_and_reference_correction(self):
        report = self.report()
        for index in range(7):
            self.assertIn(f"Question {index}?", report)
            self.assertIn(f"Reference {index}", report)
            self.assertIn(f"Reference explanation {index}", report)
        self.assertIn("**Пояснение валидатора**", report)
        self.assertIn("**Статус эталона:** Оспаривается (disputed)", report)
        self.assertIn("**Предлагаемый эталон (correctedAnswer)**", report)
        self.assertIn("Proposed corrected reference", report)
        self.assertIn("[test:1](#question-2)", report.split("## Все вопросы по категориям", 1)[0])
        self.assertIn("Ответ модели ещё не получен.", report)
        self.assertIn("Оценка валидатора отсутствует.", report)
        self.assertIn("Ответ отсутствует.", report)
        self.assertNotIn("PRIVATE CANDIDATE REASONING", report)
        self.assertNotIn("PRIVATE JUDGE REASONING", report)

    def test_cli_markdown_default_path_preserves_inputs_without_api_calls(self):
        before_answers = self.path.read_bytes()
        before_validation = self.validation_path.read_bytes()
        with patch.object(common, "build_opener", side_effect=AssertionError("no API calls")):
            code, log = self.invoke("--validation", self.validation_path, "--format", "markdown")
        self.assertEqual(code, 0, log)
        output = self.root / "model.md"
        self.assertTrue(output.is_file())
        self.assertTrue(output.read_text(encoding="utf-8").endswith("\n"))
        self.assertFalse((self.root / "model.import.json").exists())
        self.assertEqual(self.path.read_bytes(), before_answers)
        self.assertEqual(self.validation_path.read_bytes(), before_validation)

    def test_cli_explicit_path_and_no_validation(self):
        output = self.root / "nested/report.md"
        code, log = self.invoke("--format", "markdown", "--output", output)
        self.assertEqual(code, 0, log)
        report = output.read_text(encoding="utf-8")
        self.assertIn("**Баллы: 0/100**", report)
        self.assertIn("(null) — 7", report)
        self.assertIn("Файл валидации не выбран", report)
        self.assertNotIn("Валидатор: judge-model", report)

    def test_markdown_uses_selected_validation_without_legacy_verdict_fallback(self):
        self.result["answers"][4]["verdict"] = 1
        report = self.report()
        self.assertIn("[test:4](#question-5)", report.split("## Все вопросы по категориям", 1)[0])
        self.assertIn("**Баллы: 36/100**", report)

    def test_json_remains_default_and_counts_match_markdown(self):
        code, log = self.invoke("--validation", self.validation_path)
        self.assertEqual(code, 0, log)
        default = json.loads((self.root / "model.import.json").read_text())
        output = self.root / "explicit.json"
        code, log = self.invoke("--validation", self.validation_path, "--format", "json", "--output", output)
        self.assertEqual(code, 0, log)
        explicit = json.loads(output.read_text())
        self.assertEqual(default["hist"], explicit["hist"])
        self.assertEqual(default["hist"][0]["counts"], {"ok": 2, "mid": 1, "bad": 1, "skip": 3})
        self.assertEqual(default["hist"][0]["score"], 36)

    def test_markdown_cannot_overwrite_either_input_or_bench(self):
        for target in (self.path, self.validation_path, common.BENCH):
            with self.subTest(target=target):
                before = target.read_bytes()
                code, log = self.invoke("--validation", self.validation_path, "--format", "markdown",
                                        "--output", target)
                self.assertEqual(code, 1)
                self.assertIn("must not overwrite", log)
                self.assertEqual(target.read_bytes(), before)

    def test_source_hash_mismatch_keeps_existing_report(self):
        output = self.root / "report.md"
        output.write_text("Existing report\n")
        self.path.write_bytes(self.path.read_bytes() + b"\n")
        code, log = self.invoke("--validation", self.validation_path, "--format", "markdown", "--output", output)
        self.assertEqual(code, 1)
        self.assertIn("Validation source differs", log)
        self.assertEqual(output.read_text(), "Existing report\n")

    def test_atomic_markdown_failure_preserves_existing_report(self):
        output = self.root / "report.md"
        output.write_text("Existing report\n")
        with patch.object(common.os, "replace", side_effect=OSError("disk error")):
            code, log = self.invoke("--format", "markdown", "--output", output)
        self.assertEqual(code, 1)
        self.assertIn("disk error", log)
        self.assertEqual(output.read_text(), "Existing report\n")
        self.assertEqual(list(self.root.glob("*.tmp")), [])

    def test_markdown_escapes_index_and_preserves_embedded_fences(self):
        text = "```python\nx = 1\n```\n````\n<script>alert('x')</script>\n# Fake heading"
        block = export.markdown_block(text)
        self.assertEqual(block, "`````text\n" + text + "\n`````")
        self.result["answers"][0].update(question="A | B\n[link](https://example.com) <script>", answer=text)
        self.validation["answers"]["test:0"]["explanation"] = "Reason | why\n# injected"
        report = self.report()
        overview = report.split("## Все вопросы по категориям", 1)[0]
        self.assertIn(r"A \| B \[link\]", overview)
        self.assertIn("&lt;script&gt;", overview)
        self.assertIn(r"Reason \| why \# injected", overview)
        self.assertIn(block, report)

    def test_all_correct_report_has_empty_unsuccessful_groups(self):
        for index in range(7):
            self.result["answers"][index]["verdict"] = 1
        report = export.markdown_export(self.result)
        overview = report.split("## Все вопросы по категориям", 1)[0]
        self.assertIn("**Баллы: 100/100**", overview)
        self.assertNotIn("| Вопрос |", overview)
        self.assertEqual(overview.count("\nНет.\n"), 3)


if __name__ == "__main__":
    unittest.main()
