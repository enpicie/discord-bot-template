"""Template engine: cut the template down to a chosen set of optional features.

Template-only — never shipped in a generated bot. Users don't run this; the
Pages workflow runs build_site.py, which calls render() for every feature
combination and publishes the results for the generator page to download.

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
import itertools
import re
import subprocess
from pathlib import Path

TEMPLATE_ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER_NAME = "my-discord-bot"

# Order is the order the generator page shows them in.
FEATURES = {
    "dynamodb": {
        "label": "DynamoDB",
        "description": "One table for bot state, keyed per Discord server. Adds the /note example command.",
    },
    "deferred_worker": {
        "label": "Deferred worker (callbacks)",
        "description": "SQS queue + worker Lambda for commands that take longer than Discord's 3-second deadline. Adds the /slow-echo example command.",
    },
    "bot_token": {
        "label": "Bot token in Secrets Manager",
        "description": "For Discord REST API calls (roles, channel posts, guild info). Replies and callbacks don't need it.",
    },
}

# Paths owned entirely by a feature expression; dropped when it evaluates false.
FEATURE_PATHS = {
    "dynamodb": [
        "terraform/infra/dynamodb.tf",
        "src/database",
        "src/commands/notes",
        "tests/commands/test_notes_commands.py",
    ],
    "deferred_worker": [
        "terraform/infra/deferred_worker.tf",
        "jobs",
        "src/utils/deferred_dispatch.py",
        "tests/deferred_worker",
        "tests/job_imports.py",
        "tests/test_job_module_names.py",
        "src/commands/deferred_example",
        "tests/commands/test_deferred_example_commands.py",
    ],
    "bot_token": [
        "terraform/infra/secrets.tf",
        "src/utils/discord_api_helper.py",
        "tests/utils/test_discord_api_helper.py",
    ],
}

TEMPLATE_ONLY_PATHS = [
    "generator",
    "site",
    "tests/test_generator.py",
    ".github/workflows/template-ci.yml",
    ".github/workflows/pages.yml",
]

# Never part of a template render: VCS/tooling state, caches, local build output.
SKIP_PARTS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".terraform", "dist", "_site", "node_modules"}

# Names flow into AWS resource names. The tightest limit is the 64-char IAM
# role name "LambdaExecutionRole-<name>-deferred-worker-prod".
NAME_PATTERN = r"^[a-z][a-z0-9-]*[a-z0-9]$"
MAX_NAME_LEN = 64 - len("LambdaExecutionRole-") - len("-deferred-worker-prod")
PUBLIC_KEY_PATTERN = r"^[0-9a-f]{64}$"
# Files where the placeholder bot name is swapped for the real one. The
# generator page does this swap in the browser.
NAME_FILES = ["config.env", "README.md", "CLAUDE.md"]

_MARKER = re.compile(r"\[(/?)(?:feature:([a-z_+|]+)|(template-only))\]")
# Comment syntax that may wrap a marker: Python/HCL/YAML/Make `#`, Markdown `<!-- -->`.
_COMMENT_NOISE = re.compile(r"^\s*(#|<!--)?\s*|\s*(-->)?\s*$")
_TRAILING_MARKER = re.compile(r"\s*(#|<!--)?\s*\[(?:feature:[a-z_+|]+|template-only)\]\s*(-->)?\s*$")


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


def _is_dropped(rel: str, enabled: set) -> bool:
    def under(prefix: str) -> bool:
        return rel == prefix or rel.startswith(prefix + "/")

    if any(under(p) for p in TEMPLATE_ONLY_PATHS):
        return True
    return any(
        not evaluate(expression, enabled) and any(under(p) for p in paths)
        for expression, paths in FEATURE_PATHS.items()
    )


def _template_files(root: Path) -> list:
    """Every file git would ship: tracked plus new-but-not-ignored, as posix paths.

    Asking git (instead of walking the folder) keeps gitignored local files —
    .env, .claude/, editor state — out of the bundles on a developer machine.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        capture_output=True, check=True,
    )
    return sorted({p for p in result.stdout.decode("utf-8").split("\0") if p})


def render(enabled: set, root: Path = TEMPLATE_ROOT) -> dict:
    """Return {relative posix path: text} for a bot with `enabled` features.

    The bot keeps PLACEHOLDER_NAME; the generator page swaps in the real name.
    Every template file must be UTF-8 text — the page builds the zip from text.
    """
    files = {}
    for rel in _template_files(root):
        path = root / rel
        if any(part in SKIP_PARTS for part in rel.split("/")) or not path.is_file():
            continue
        if _is_dropped(rel, enabled):
            continue
        try:
            text = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError as e:
            raise TemplateError(f"{rel} is not UTF-8 text; the generator only ships text files") from e
        # Normalize to LF so output is identical whichever OS built it.
        text = process_text(text.replace("\r\n", "\n"), enabled, source=rel)
        if _MARKER.search(text):
            raise TemplateError(f"{rel}: marker left after rendering")
        files[rel] = text
    return files


def apply_name(files: dict, name: str, public_key_dev: str = "", public_key_prod: str = "") -> dict:
    """Swap in the bot's name and public keys.

    MIRROR: site/generator.js applyName — the page does this in the browser.
    This copy exists for the tests; keep the two in sync.
    """
    out = dict(files)
    for rel in NAME_FILES:
        if rel in out:
            out[rel] = out[rel].replace(PLACEHOLDER_NAME, name)
    config = out["config.env"]
    if public_key_dev:
        config = re.sub(r"^DISCORD_PUBLIC_KEY_DEV=.*$", f"DISCORD_PUBLIC_KEY_DEV={public_key_dev}", config, flags=re.M)
    if public_key_prod:
        config = re.sub(r"^DISCORD_PUBLIC_KEY_PROD=.*$", f"DISCORD_PUBLIC_KEY_PROD={public_key_prod}", config, flags=re.M)
    out["config.env"] = config
    return out


def validate_name(name: str) -> None:
    if not re.match(NAME_PATTERN, name):
        raise TemplateError("Name must be lowercase letters, digits and hyphens, starting with a letter.")
    if name == PLACEHOLDER_NAME:
        raise TemplateError(f"Pick a real name; {PLACEHOLDER_NAME!r} is the template placeholder.")
    if len(name) > MAX_NAME_LEN:
        raise TemplateError(f"Name is {len(name)} chars; max is {MAX_NAME_LEN} (AWS IAM role names cap at 64).")


def combination_key(enabled: set) -> str:
    """Stable file name for a feature set, e.g. 'bot_token+dynamodb' or 'base'.

    MIRROR: site/generator.js combinationKey — keep in sync.
    """
    return "+".join(sorted(enabled)) or "base"


def all_combinations():
    """Every feature subset."""
    names = list(FEATURES)
    for flags in itertools.product([True, False], repeat=len(names)):
        yield {n for n, on in zip(names, flags) if on}
