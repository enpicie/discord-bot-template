"""Template-only: tests for init_bot.py. Removed from generated bots.

The full check (each generated bot's own make test / make lint / terraform
validate) runs in .github/workflows/template-ci.yml; these are the fast checks.
"""
import os
import py_compile
import shutil
import sys
import tempfile
import unittest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import init_bot  # noqa: E402 — imported after sys.path bootstrap

ALL = set(init_bot.FEATURES)


class TestProcessText(unittest.TestCase):
    def test_inline_marker_keeps_line_without_marker_when_enabled(self):
        text = "x = 1  # [feature:dynamodb]\n"
        self.assertEqual(init_bot.process_text(text, {"dynamodb"}), "x = 1\n")

    def test_inline_marker_drops_line_when_disabled(self):
        text = "a = 0\nx = 1  # [feature:dynamodb]\n"
        self.assertEqual(init_bot.process_text(text, set()), "a = 0\n")

    def test_block_markers_drop_or_keep_whole_block(self):
        text = "a\n# [feature:bot_token]\nb\nc\n# [/feature:bot_token]\nd\n"
        self.assertEqual(init_bot.process_text(text, {"bot_token"}), "a\nb\nc\nd\n")
        self.assertEqual(init_bot.process_text(text, set()), "a\nd\n")

    def test_and_or_expressions(self):
        both = "x  # [feature:dynamodb+examples]\n"
        either = "y  # [feature:dynamodb|deferred_worker]\n"
        self.assertEqual(init_bot.process_text(both, {"dynamodb"}), "")
        self.assertEqual(init_bot.process_text(both, {"dynamodb", "examples"}), "x\n")
        self.assertEqual(init_bot.process_text(either, {"deferred_worker"}), "y\n")
        self.assertEqual(init_bot.process_text(either, set()), "")

    def test_markdown_markers(self):
        text = "<!-- [feature:examples] -->\nhi\n<!-- [/feature:examples] -->\n- item  <!-- [feature:examples] -->\n"
        self.assertEqual(init_bot.process_text(text, {"examples"}), "hi\n- item\n")

    def test_template_only_is_always_removed(self):
        text = "keep\n# [template-only]\ngone\n# [/template-only]\nalso gone  # [template-only]\n"
        self.assertEqual(init_bot.process_text(text, ALL), "keep\n")

    def test_nested_block_needs_every_enclosing_feature(self):
        text = "# [feature:dynamodb]\n# [feature:deferred_worker]\nx\n# [/feature:deferred_worker]\n# [/feature:dynamodb]\n"
        self.assertEqual(init_bot.process_text(text, {"deferred_worker"}), "")
        self.assertEqual(init_bot.process_text(text, {"dynamodb", "deferred_worker"}), "x\n")

    def test_crlf_line_endings_are_preserved(self):
        text = "a\r\nx = 1  # [feature:dynamodb]\r\n"
        self.assertEqual(init_bot.process_text(text, {"dynamodb"}), "a\r\nx = 1\r\n")

    def test_malformed_markers_raise(self):
        for bad in (
            "x  # [feature:nope]\n",                                    # unknown feature
            "# [feature:dynamodb]\nx\n",                                 # unclosed
            "x\n# [/feature:dynamodb]\n",                                # stray close
            "y = f([feature:dynamodb])\n",                               # marker not trailing
            "x  # [feature:dynamodb+examples|bot_token]\n",              # mixed operators
        ):
            with self.subTest(bad=bad), self.assertRaises(init_bot.TemplateError):
                init_bot.process_text(bad, ALL)


class TestValidateName(unittest.TestCase):
    def test_accepts_a_normal_name(self):
        init_bot.validate_name("my-cool-bot")

    def test_rejects_bad_names(self):
        for bad in ("My-Bot", "bot_", "-bot", "1bot", init_bot.PLACEHOLDER_NAME, "a" * (init_bot._MAX_NAME_LEN + 1)):
            with self.subTest(name=bad), self.assertRaises(init_bot.TemplateError):
                init_bot.validate_name(bad)


class TestGenerateEveryCombination(unittest.TestCase):
    """Generate every feature subset into a temp copy of the repo."""

    def _generate(self, enabled: set) -> str:
        tmp = tempfile.mkdtemp(prefix="init-bot-")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        dest = os.path.join(tmp, "bot")
        shutil.copytree(_REPO_ROOT, dest, ignore=shutil.ignore_patterns(*init_bot.SKIP_DIRS))
        init_bot.generate(init_bot.Path(dest), "test-bot", enabled)
        return dest

    def test_every_combination_generates_clean_compilable_output(self):
        for enabled in init_bot.all_combinations():
            with self.subTest(enabled=sorted(enabled)):
                dest = self._generate(enabled)

                for rel in init_bot.TEMPLATE_ONLY_PATHS:
                    self.assertFalse(os.path.exists(os.path.join(dest, rel)), rel)
                for expression, paths in init_bot.FEATURE_PATHS.items():
                    kept = init_bot.evaluate(expression, enabled)
                    for rel in paths:
                        self.assertEqual(os.path.exists(os.path.join(dest, rel)), kept, rel)

                with open(os.path.join(dest, "config.env"), encoding="utf-8") as f:
                    config = f.read()
                self.assertIn("APP_NAME=test-bot", config)
                self.assertNotIn(init_bot.PLACEHOLDER_NAME, config)

                for root, _, files in os.walk(dest):
                    for name in files:
                        if name.endswith(".py"):
                            py_compile.compile(os.path.join(root, name), doraise=True)


if __name__ == "__main__":
    unittest.main()
