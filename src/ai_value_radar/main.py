from __future__ import annotations

import argparse
import json
import sys

from .config import Settings, ensure_data_dirs
from .pipeline import run_scan
from .telegram import send_test


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI VALUE RADAR v0.1")
    parser.add_argument("--telegram-test", action="store_true", help="send one safe Telegram test message")
    args = parser.parse_args(argv)
    ensure_data_dirs()
    if args.telegram_test:
        try:
            print(json.dumps({"telegram": send_test()}, ensure_ascii=False))
            return 0
        except Exception as exc:
            print(json.dumps({"telegram": "error", "error": type(exc).__name__}, ensure_ascii=False))
            return 1
    try:
        report = run_scan(Settings.from_env())
    except Exception as exc:
        # Keep the CLI failure concise and never print environment variables.
        print(json.dumps({"status": "error", "error": type(exc).__name__}, ensure_ascii=False))
        return 1
    print(
        json.dumps(
            {
                "status": "ok",
                "fetched": report.get("fetched_count", 0),
                "new": report.get("new_count", 0),
                "promising": report.get("promising_count", 0),
                "top3": report.get("top3_count", 0),
                "drafts": report.get("draft_count", 0),
                "telegram": report.get("notification", {}).get("status"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
