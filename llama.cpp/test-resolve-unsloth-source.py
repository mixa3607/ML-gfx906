import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "resolver", Path(__file__).with_name("resolve-unsloth-source.py")
)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ResolveSourceTest(unittest.TestCase):
    def setUp(self):
        self.tag = "b11734-mix-c208e5f"
        self.name = f"llama.cpp-source-{self.tag}.tar.gz"
        self.url = f"https://github.com/unslothai/llama.cpp/releases/download/{self.tag}/{self.name}"
        self.release = {
            "tag_name": self.tag,
            "draft": False,
            "assets": [{"name": self.name, "browser_download_url": self.url, "digest": "sha256:" + "a" * 64}],
        }

    def test_merged_source(self):
        self.assertEqual(resolver.resolve_source(self.release, self.tag), (self.url, "a" * 64))

    def test_refuses_invalid_release(self):
        for changes in ({"tag_name": "other"}, {"draft": True}, {"assets": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                resolver.resolve_source(self.release | changes, self.tag)

    def test_refuses_unverified_asset(self):
        for changes in ({"digest": None}, {"digest": "sha256:bad"}, {"browser_download_url": "https://example.com/source.tar.gz"}):
            release = copy.deepcopy(self.release)
            release["assets"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                resolver.resolve_source(release, self.tag)


if __name__ == "__main__":
    unittest.main()
