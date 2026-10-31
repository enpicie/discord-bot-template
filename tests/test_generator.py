"""Template-only: tests for generator/engine.py and build_site.py. Never shipped.

The full check (unzip what the page builds, then run that bot's own make test /
make lint / terraform validate) runs in .github/workflows/template-ci.yml.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

_GENERATOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "generator"))
if _GENERATOR_DIR not in sys.path:
    sys.path.insert(0, _GENERATOR_DIR)

import build_site  # noqa: E402 — imported after sys.path bootstrap
import engine  # noqa: E402

ALL = set(engine.FEATURES)


class TestProcessText(unittest.TestCase):
    def test_inline_marker_keeps_line_without_marker_when_enabled(self):
        text = "x = 1  # [feature:dynamodb]\n"
        self.assertEqual(engine.process_text(text, {"dynamodb"}), "x = 1\n")

    def test_inline_marker_drops_line_when_disabled(self):
        text = "a = 0\nx = 1  # [feature:dynamodb]\n"
        self.assertEqual(engine.process_text(text, set()), "a = 0\n")

    def test_block_markers_drop_or_keep_whole_block(self):
        text = "a\n# [feature:bot_token]\nb\nc\n# [/feature:bot_token]\nd\n"
        self.assertEqual(engine.process_text(text, {"bot_token"}), "a\nb\nc\nd\n")
        self.assertEqual(engine.process_text(text, set()), "a\nd\n")

    def test_and_or_expressions(self):
        both = "x  # [feature:dynamodb+bot_token]\n"
        either = "y  # [feature:dynamodb|deferred_worker]\n"
        self.assertEqual(engine.process_text(both, {"dynamodb"}), "")
        self.assertEqual(engine.process_text(both, {"dynamodb", "bot_token"}), "x\n")
        self.assertEqual(engine.process_text(either, {"deferred_worker"}), "y\n")
        self.assertEqual(engine.process_text(either, set()), "")

    def test_markdown_markers(self):
        text = "<!-- [feature:bot_token] -->\nhi\n<!-- [/feature:bot_token] -->\n- item  <!-- [feature:bot_token] -->\n"
        self.assertEqual(engine.process_text(text, {"bot_token"}), "hi\n- item\n")

    def test_template_only_is_always_removed(self):
        text = "keep\n# [template-only]\ngone\n# [/template-only]\nalso gone  # [template-only]\n"
        self.assertEqual(engine.process_text(text, ALL), "keep\n")

    def test_nested_block_needs_every_enclosing_feature(self):
        text = "# [feature:dynamodb]\n# [feature:deferred_worker]\nx\n# [/feature:deferred_worker]\n# [/feature:dynamodb]\n"
        self.assertEqual(engine.process_text(text, {"deferred_worker"}), "")
        self.assertEqual(engine.process_text(text, {"dynamodb", "deferred_worker"}), "x\n")

    def test_malformed_markers_raise(self):
        for bad in (
            "x  # [feature:nope]\n",                                    # unknown feature
            "# [feature:dynamodb]\nx\n",                                 # unclosed
            "x\n# [/feature:dynamodb]\n",                                # stray close
            "y = f([feature:dynamodb])\n",                               # marker not trailing
            "x  # [feature:dynamodb+deferred_worker|bot_token]\n",            # mixed operators
        ):
            with self.subTest(bad=bad), self.assertRaises(engine.TemplateError):
                engine.process_text(bad, ALL)


class TestNameRules(unittest.TestCase):
    def test_accepts_a_normal_name(self):
        engine.validate_name("my-cool-bot")

    def test_rejects_bad_names(self):
        for bad in ("My-Bot", "bot_", "-bot", "1bot", engine.PLACEHOLDER_NAME, "a" * (engine.MAX_NAME_LEN + 1)):
            with self.subTest(name=bad), self.assertRaises(engine.TemplateError):
                engine.validate_name(bad)

    def test_apply_name_swaps_name_and_keys(self):
        files = engine.render(ALL)
        named = engine.apply_name(files, "score-bot", "a" * 64, "")
        self.assertIn("APP_NAME=score-bot", named["config.env"])
        self.assertIn("DISCORD_PUBLIC_KEY_DEV=" + "a" * 64, named["config.env"])
        self.assertNotIn("DISCORD_PUBLIC_KEY_PROD=" + "a" * 64, named["config.env"])
        for rel in engine.NAME_FILES:
            self.assertNotIn(engine.PLACEHOLDER_NAME, named[rel], rel)


class TestRenderEveryCombination(unittest.TestCase):
    def test_every_combination_renders_clean_compilable_output(self):
        for enabled in engine.all_combinations():
            with self.subTest(enabled=sorted(enabled)):
                files = engine.render(enabled)

                for rel in files:
                    self.assertFalse(engine._is_dropped(rel, enabled), rel)
                for expression, paths in engine.FEATURE_PATHS.items():
                    if engine.evaluate(expression, enabled):
                        for rel in paths:
                            self.assertTrue(any(f == rel or f.startswith(rel + "/") for f in files), rel)
                self.assertFalse(any(f.startswith(("generator/", "site/")) for f in files))
                # Only files git would ship — never gitignored local state.
                self.assertFalse(any(f.startswith((".claude/", ".venv/", "_site/")) or f == ".env" for f in files))

                for rel, text in files.items():
                    if rel.endswith(".py"):
                        compile(text, rel, "exec")

    def test_build_site_writes_manifest_and_every_bundle(self):
        out = tempfile.mkdtemp(prefix="site-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        build_site.build(engine.Path(out) / "_site")

        manifest = json.loads((engine.Path(out) / "_site" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["bundles"]), 2 ** len(engine.FEATURES))
        for key in manifest["bundles"]:
            self.assertTrue((engine.Path(out) / "_site" / "bundles" / f"{key}.json").exists(), key)
        for page_file in ("index.html", "app.js", "generator.js", "style.css"):
            self.assertTrue((engine.Path(out) / "_site" / page_file).exists(), page_file)
        self.assertFalse((engine.Path(out) / "_site" / "test").exists())


if __name__ == "__main__":
    unittest.main()
