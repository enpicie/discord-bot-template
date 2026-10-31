"""Build the generator site into an output directory (default: _site/).

Template-only. Run by .github/workflows/pages.yml (and template-ci.yml):

    python generator/build_site.py [--out _site]

Writes:
  index.html, generator.js, app.js, style.css   copied from site/
  manifest.json                                  features, name rules, combination keys
  bundles/<key>.json                             {path: text} for each feature combination
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import engine


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(engine.TEMPLATE_ROOT / "site", out, ignore=shutil.ignore_patterns("test", "*.md"))
    (out / "bundles").mkdir()

    keys = []
    for enabled in engine.all_combinations():
        key = engine.combination_key(enabled)
        files = engine.render(enabled)
        (out / "bundles" / f"{key}.json").write_text(json.dumps(files, sort_keys=True), encoding="utf-8")
        keys.append(key)
        print(f"bundle {key}: {len(files)} files")

    manifest = {
        "placeholder_name": engine.PLACEHOLDER_NAME,
        "name_pattern": engine.NAME_PATTERN,
        "max_name_len": engine.MAX_NAME_LEN,
        "public_key_pattern": engine.PUBLIC_KEY_PATTERN,
        "name_files": engine.NAME_FILES,
        "features": [{"key": k, **v} for k, v in engine.FEATURES.items()],
        "bundles": sorted(keys),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"site built in {out}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(engine.TEMPLATE_ROOT / "_site"))
    args = parser.parse_args(argv)
    try:
        build(Path(args.out))
    except engine.TemplateError as e:
        print(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
