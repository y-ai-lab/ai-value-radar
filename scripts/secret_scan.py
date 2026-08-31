from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
EXCLUDED_PARTS = {".git", "__pycache__", ".venv", "venv", ".pytest_cache"}
PUBLIC_URL_PATTERN = re.compile(r"https?://[^\s\"'<>]+")


def candidate_files() -> list[Path]:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=False,
        )
        paths = [ROOT / value for value in completed.stdout.decode().split("\0") if value]
    except (OSError, subprocess.CalledProcessError):
        paths = [path for path in ROOT.rglob("*") if path.is_file()]
    return [path for path in paths if not EXCLUDED_PARTS.intersection(path.parts)]


def _match_is_public_url_path(content: str, match: re.Match[str]) -> bool:
    """Avoid false positives from ordinary URL slugs such as ``/musk-...``.

    A key-shaped value in a URL query string is still treated as a secret.
    Only a match fully contained in the path portion of an HTTP(S) URL is
    ignored. This keeps public feed URLs scannable without weakening checks
    for credentials pasted into query parameters or normal text.
    """
    for url_match in PUBLIC_URL_PATTERN.finditer(content):
        if not (url_match.start() <= match.start() and match.end() <= url_match.end()):
            continue
        raw_url = url_match.group().rstrip(".,;:)]}")
        parsed = urlsplit(raw_url)
        if parsed.query or parsed.fragment or not parsed.netloc:
            return False
        path_start = url_match.start() + len(f"{parsed.scheme}://{parsed.netloc}")
        path_end = path_start + len(parsed.path)
        return path_start <= match.start() and match.end() <= path_end
    return False


def contains_secret_pattern(content: str) -> bool:
    for pattern in PATTERNS:
        for match in pattern.finditer(content):
            if pattern.pattern == r"sk-[A-Za-z0-9_-]{20,}" and _match_is_public_url_path(content, match):
                continue
            return True
    return False


def main() -> int:
    hits: list[str] = []
    for path in candidate_files():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if contains_secret_pattern(content):
            hits.append(str(path.relative_to(ROOT)))
    if hits:
        print("Potential secret pattern found in: " + ", ".join(hits))
        return 1
    print("Secret scan: 0 potential secrets found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
