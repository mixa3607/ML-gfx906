import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import freeze


class ByteTokenizer:
    def encode(self, text, parse_special=False):
        return list(text.encode())

    def token_bytes(self, token):
        return bytes([token])

    def decode(self, ids):
        return bytes(ids).decode('utf-8', errors='replace')


class Template:
    def render(self, messages, **kwargs):
        return '<user>' + messages[0]['content'] + '<assistant>'


class FreezeTests(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {'split': split, 'pageid': pageid, 'title': 'Article', 'text': 'Проза ' * 100}
            for pageid, split in enumerate(('warmup', 'warmup', 'measurement', 'measurement'))
        ]
        self.suite = SimpleNamespace(
            SEED=42, TG=256, WARMUP_PP=[101, 150], MEASUREMENT_PP=[203, 501, 199],
            ASSISTANT_SUFFIX='<assistant>', RENDER_KWARGS={},
        )

    def build(self):
        return list(freeze.build_cases(
            self.sources, ['Explain', 'Summarise'], self.suite, ByteTokenizer(), Template(),
        ))

    def test_schedule_and_passages(self):
        cases = self.build()
        self.assertEqual(cases, self.build())
        self.assertEqual([case['pp'] for case in cases], [101, 150, 203, 501, 199])
        self.assertEqual([case['phase'] for case in cases], ['warmup'] * 2 + ['measurement'] * 3)
        offsets = {}
        for case, instruction in zip(cases, ['Explain', 'Summarise', 'Explain', 'Summarise', 'Explain']):
            self.assertEqual(len(case['ids']), case['pp'])
            self.assertEqual(case['tg'], 256)
            self.assertTrue(case['prompt'].endswith('<assistant>'))
            self.assertIn(instruction, case['prompt'])
            for passage in case['passages']:
                pageid = passage['pageid']
                start, end = passage['start_byte'], passage['end_byte']
                self.assertGreaterEqual(start, offsets.get(pageid, 0))
                self.assertGreater(end, start)
                self.assertLessEqual(end, len(self.sources[pageid]['text'].encode()))
                offsets[pageid] = end

    def test_insufficient_source(self):
        self.suite.WARMUP_PP = [10000]
        with self.assertRaisesRegex(ValueError, 'only .* available'):
            self.build()

    def test_no_room_for_prose(self):
        self.suite.WARMUP_PP = [20]
        with self.assertRaisesRegex(ValueError, 'no room for source prose'):
            self.build()

    def test_source_exhausted(self):
        self.suite.WARMUP_PP = [200] * 100
        with self.assertRaisesRegex(ValueError, 'source corpus exhausted|only .* available'):
            self.build()

    def test_request_spans_articles(self):
        self.suite.WARMUP_PP = [1500]
        case = self.build()[0]
        self.assertEqual(len(case['passages']), 2)
        self.assertEqual(len(case['ids']), 1500)

    def test_changed_assistant_header(self):
        self.suite.ASSISTANT_SUFFIX = '<different>'
        with self.assertRaisesRegex(ValueError, 'ASSISTANT_SUFFIX'):
            self.build()

    def test_fetch_article_titles(self):
        corpus = freeze.load_config(freeze.ROOT / 'corpora/ru-prose/corpus.py')
        article = {'extract': 'Article text', 'title': 'Article', 'pageid': 1,
                   'revisions': [{'revid': 2}]}
        response = json.dumps({'query': {'pages': {'1': article}}}).encode()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            with (
                patch.object(freeze, 'load_config', return_value=corpus),
                patch.object(freeze.urllib.request, 'urlopen',
                             side_effect=lambda *a, **kw: io.BytesIO(response)) as get,
                patch.object(freeze.time, 'sleep'),
                patch('builtins.print'),
            ):
                freeze.fetch(path)
            self.assertEqual(get.call_count, 36)
            rows = [json.loads(line) for line in (path / 'sources.jsonl').read_text().splitlines()]
            self.assertEqual({row['split'] for row in rows}, {'warmup', 'measurement'})


if __name__ == '__main__':
    unittest.main()
