#!/usr/bin/env python3
"""Turn a fresh copy of discord-bot-template into a new bot repo.

Run once, from the root of the new repo:

    python init_bot.py                      # interactive
    python init_bot.py --name my-bot --no-dynamodb --yes

It names the bot, removes the optional features you don't want, deletes the
template-only files (including this script), and prints the remaining one-time
setup as copyable commands. Standard library only.

How features are cut: every line that belongs to an optional feature carries a
marker comment. A trailing marker covers one line:

    DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME")  # [feature:dynamodb]

A marker alone on its line opens or closes a block:

    # [feature:deferred_worker]
    ...
    # [/feature:deferred_worker]

`a+b` means "only if both features are kept", `a|b` "if either is kept".
`[template-only]` content is always removed. Kept content has its markers
stripped, so the generated repo reads like hand-written code. Whole files and
directories that belong to one feature are listed in FEATURE_PATHS.
"""
import argparse
import itertools
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE_REPO = "enpicie/discord-bot-template"
PLACEHOLDER_NAME = "my-discord-bot"

FEATURES = {
    "dynamodb": "DynamoDB table for bot state",
    "deferred_worker": "Deferred worker (SQS + Lambda) for commands that take over 3s",
    "bot_token": "Bot token in Secrets Manager, for Discord REST API calls",
    "examples": "Example commands (/note-*, /slow-echo, /server-info) to learn from",
}

# Paths owned entirely by a feature expression; removed when it evaluates false.
FEATURE_PATHS = {
    "dynamodb": [
        "terraform/infra/dynamodb.tf",
        "src/database",
    ],
    "deferred_worker": [
        "terraform/infra/deferred_worker.tf",
        "jobs",
        "src/utils/deferred_dispatch.py",
        "tests/deferred_worker",
        "tests/job_imports.py",
        "tests/test_job_module_names.py",
    ],
    "bot_token": [
        "terraform/infra/secrets.tf",
        "src/utils/discord_api_helper.py",
        "tests/utils/test_discord_api_helper.py",
    ],
    "dynamodb+examples": [
        "src/commands/notes",
        "tests/commands/test_notes_commands.py",
    ],
    "deferred_worker+examples": [
        "src/commands/deferred_example",
        "tests/commands/test_deferred_example_commands.py",
        "jobs/deferred_worker/slow_echo_commands.py",
    ],
}

TEMPLATE_ONLY_PATHS = [
    "init_bot.py",
    "tests/test_init_bot.py",
    ".github/workflows/template-ci.yml",
]

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".terraform", "dist", "node_modules"}

_MARKER = re.compile(r"\[(/?)(?:feature:([a-z_+|]+)|(template-only))\]")
# Comment syntax that may wrap a marker: Python/HCL/YAML/Make `#`, Markdown `<!-- -->`.
_COMMENT_NOISE = re.compile(r"^\s*(#|<!--)?\s*|\s*(-->)?\s*$")
_TRAILING_MARKER = re.compile(r"\s*(#|<!--)?\s*\[(?:feature:[a-z_+|]+|template-only)\]\s*(-->)?\s*$")

# Names flow into AWS resource names. The tightest limit is the 64-char IAM
# role name "LambdaExecutionRole-<name>-deferred-worker-prod".
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
_MAX_NAME_LEN = 64 - len("LambdaExecutionRole-") - len("-deferred-worker-prod")
_PUBLIC_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class TemplateError(Exception):
    """Raised for malformed markers or invalid input."""


def evaluate(expression: str | None, enabled: set) -> bool:
    """Evaluate a marker expression (None means [template-only])."""
    if expression is None:
        return False
    if "+" in expression and "|" in expression:
        raise TemplateError(f"Mixed '+' and '|' in marker expression: {expression!r}")
    names = re.split(r"[+|]", expression)
    unknown = [n for n in names if n not in FEATURES]
    if unknown:
        raise TemplateError(f"Unknown feature(s) {unknown} in marker expression {expression!r}")
    if "|" in expression:
        return any(n in enabled for n in names)
    return all(n in enabled for n in names)


def process_text(text: str, enabled: set, source: str = "<text>") -> str:
    """Apply feature markers to one file's text and return the result."""
    out = []
    stack = []  # (expression, kept) for open blocks
    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        match = _MARKER.search(line)
        if match is None:
            if all(kept for _, kept in stack):
                out.append(line)
            continue

        closing, feature_expr, template_only = match.groups()
        expression = feature_expr if template_only is None else None
        is_delimiter = _COMMENT_NOISE.sub("", _MARKER.sub("", line, count=1)) == ""

        if is_delimiter:
            if closing:
                if not stack or stack[-1][0] != expression:
                    raise TemplateError(f"{source}:{lineno}: closing marker does not match an open block")
                stack.pop()
            else:
                stack.append((expression, evaluate(expression, enabled)))
            continue

        if closing:
            raise TemplateError(f"{source}:{lineno}: closing marker must be on its own line")
        if not _TRAILING_MARKER.search(line):
            raise TemplateError(f"{source}:{lineno}: inline marker must be at the end of the line")
        if all(kept for _, kept in stack) and evaluate(expression, enabled):
            body = line.rstrip("\r\n")
            out.append(_TRAILING_MARKER.sub("", body) + line[len(body):])

    if stack:
        raise TemplateError(f"{source}: unclosed marker block {stack[-1][0] or 'template-only'!r}")

    result = "".join(out)
    # Removing blocks can leave stacked blank lines; never keep more than two.
    result = re.sub(r"(\r?\n)(?:\r?\n){3,}", r"\1\1\1", result)
    return result.rstrip("\n") + "\n" if result.strip() else result


def _iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        yield path, text


def _remove(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _remove_empty_dirs(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()) and not any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            path.rmdir()


def generate(root: Path, name: str, enabled: set, public_key_dev: str = "", public_key_prod: str = "") -> None:
    """Rewrite the repo at `root` in place into a bot named `name` with `enabled` features."""
    for expression, paths in FEATURE_PATHS.items():
        if not evaluate(expression, enabled):
            for rel in paths:
                _remove(root / rel)
    for rel in TEMPLATE_ONLY_PATHS:
        _remove(root / rel)
    _remove_empty_dirs(root)

    for path, text in _iter_text_files(root):
        new_text = process_text(text, enabled, source=str(path.relative_to(root)))
        if path.name in ("config.env", "README.md", "CLAUDE.md"):
            new_text = new_text.replace(PLACEHOLDER_NAME, name)
        if path.name == "config.env":
            if public_key_dev:
                new_text = re.sub(r"^DISCORD_PUBLIC_KEY_DEV=.*$", f"DISCORD_PUBLIC_KEY_DEV={public_key_dev}", new_text, flags=re.M)
            if public_key_prod:
                new_text = re.sub(r"^DISCORD_PUBLIC_KEY_PROD=.*$", f"DISCORD_PUBLIC_KEY_PROD={public_key_prod}", new_text, flags=re.M)
        if new_text != text:
            path.write_bytes(new_text.encode("utf-8"))

    leftovers = [str(p.relative_to(root)) for p, t in _iter_text_files(root) if _MARKER.search(t)]
    if leftovers:
        raise TemplateError(f"Markers left after generation in: {leftovers}")


def validate_name(name: str) -> None:
    if not _NAME_PATTERN.match(name):
        raise TemplateError("Name must be lowercase letters, digits and hyphens, starting with a letter.")
    if name == PLACEHOLDER_NAME:
        raise TemplateError(f"Pick a real name; {PLACEHOLDER_NAME!r} is the template placeholder.")
    if len(name) > _MAX_NAME_LEN:
        raise TemplateError(
            f"Name is {len(name)} chars; max is {_MAX_NAME_LEN} so AWS IAM role names "
            "(LambdaExecutionRole-<name>-deferred-worker-prod) stay under 64 chars."
        )


def _origin_is_template(root: Path) -> bool:
    if not (root / ".git").exists():
        return False
    try:
        url = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=False,
        ).stdout
    except FileNotFoundError:
        return False
    return TEMPLATE_REPO in url


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    answer = _ask(f"{prompt} (y/n)", "y" if default else "n").lower()
    return answer.startswith("y")


def _next_steps(name: str, enabled: set, keys_set: bool) -> str:
    keys_step = "" if keys_set else (
        "  - Copy each app's Public Key into DISCORD_PUBLIC_KEY_DEV / _PROD in config.env\n"
    )
    return f"""
Done. {name} is ready with: {", ".join(sorted(enabled)) or "base only"}.

Remaining one-time setup:

1. Discord Developer Portal (https://discord.com/developers/applications):
   create a dev app and a prod app.
{keys_step}
2. Repo variables and secrets (run from this repo; each secret prompts for its value):

    gh variable set DISCORD_APP_ID_DEV --body <dev application id>
    gh variable set DISCORD_APP_ID_PROD --body <prod application id>
    gh secret set DISCORD_BOT_TOKEN_DEV
    gh secret set DISCORD_BOT_TOKEN_PROD

3. Commit and deploy dev (any non-main branch deploys dev):

    git add -A
    git commit -m "Initialize {name} from discord-bot-template"
    git push
    git checkout -b dev
    git push -u origin dev

4. Copy the interactions_endpoint_url from the deploy log into the dev app's
   Interactions Endpoint URL, then run the Dev Pipeline from the Actions tab
   with "Run Discord command registration" checked.
"""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Initialize a new bot from discord-bot-template.")
    parser.add_argument("--name", help="Bot name, used for every AWS resource (lowercase, hyphens)")
    for feature, description in FEATURES.items():
        parser.add_argument(f"--no-{feature.replace('_', '-')}", action="store_true", help=f"Drop: {description}")
    parser.add_argument("--public-key-dev", default="", help="Dev Discord app public key (64 hex chars)")
    parser.add_argument("--public-key-prod", default="", help="Prod Discord app public key (64 hex chars)")
    parser.add_argument("--yes", action="store_true", help="Don't prompt; keep every feature not dropped by a flag")
    args = parser.parse_args(argv)

    if PLACEHOLDER_NAME not in (ROOT / "config.env").read_text(encoding="utf-8"):
        print("This repo has already been initialized (config.env has no placeholder name).")
        return 1
    if _origin_is_template(ROOT):
        print(
            f"origin points at {TEMPLATE_REPO} itself. Create your bot's repo first:\n\n"
            f"    gh repo create <owner>/<bot-name> --template {TEMPLATE_REPO} --private --clone\n"
        )
        return 1

    interactive = not args.yes and sys.stdin.isatty()
    name = args.name or ""
    while interactive and not name:
        name = _ask("Bot name (lowercase, hyphens)")
        try:
            validate_name(name)
        except TemplateError as e:
            print(f"  {e}")
            name = ""
    if not name:
        parser.error("--name is required when not running interactively")

    enabled = set()
    for feature, description in FEATURES.items():
        dropped = getattr(args, f"no_{feature}")
        if dropped:
            continue
        if not interactive or _ask_yes_no(f"Include {description}?"):
            enabled.add(feature)

    public_key_dev = args.public_key_dev or (_ask("Dev app public key (blank to fill in later)") if interactive else "")
    public_key_prod = args.public_key_prod or (_ask("Prod app public key (blank to fill in later)") if interactive else "")

    try:
        validate_name(name)
        for key in (public_key_dev, public_key_prod):
            if key and not _PUBLIC_KEY_PATTERN.match(key):
                raise TemplateError("Public keys are 64 lowercase hex characters (Developer Portal > General Information).")
        generate(ROOT, name, enabled, public_key_dev, public_key_prod)
    except TemplateError as e:
        print(f"Error: {e}")
        return 1

    print(_next_steps(name, enabled, keys_set=bool(public_key_dev and public_key_prod)))
    return 0


def all_combinations():
    """Every feature subset — used by the template's own tests and CI."""
    names = list(FEATURES)
    for flags in itertools.product([True, False], repeat=len(names)):
        yield {n for n, on in zip(names, flags) if on}


if __name__ == "__main__":
    sys.exit(main())
