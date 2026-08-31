from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


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


def main() -> int:
    hits: list[str] = []
    for path in candidate_files():
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(pattern.search(content) for pattern in PATTERNS):
            hits.append(str(path.relative_to(ROOT)))
    if hits:
        print("Potential secret pattern found in: " + ", ".join(hits))
        return 1
    print("Secret scan: 0 potential secrets found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
