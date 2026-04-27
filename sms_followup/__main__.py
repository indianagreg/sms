from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from .analyze import analyze_threads
from .config import load_config
from .emailer import send_email
from .messages import load_threads
from .render import render_email
from .state import FollowupState


def main() -> int:
    parser = argparse.ArgumentParser(description="Email a daily SMS follow-up digest.")
    parser.add_argument("--config", default="config.json", help="Path to config JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Print the email instead of sending it.")
    parser.add_argument("--include-reported", action="store_true", help="Include items already reported previously.")
    parser.add_argument("--test-email", action="store_true", help="Send a simple test email without reading Messages.")
    args = parser.parse_args()

    _load_dotenv(Path(".env"))
    config = load_config(Path(args.config))

    if args.test_email:
        subject = f"{config.email.subject_prefix}: test"
        body = "SMS follow-up digest email delivery is configured.\n"
        if args.dry_run:
            print(f"Subject: {subject}\n")
            print(body)
            return 0
        send_email(subject, body, config)
        print(f"Sent test email to {config.email.to_address}")
        return 0

    state = FollowupState(Path(config.state_path).expanduser())

    try:
        threads = load_threads(config)
        findings = analyze_threads(threads, config)
    except PermissionError as exc:
        print(
            "Could not read the macOS Messages database. Give Terminal or your Python runtime "
            "Full Disk Access in System Settings -> Privacy & Security -> Full Disk Access, "
            f"then run again.\n\nDetails: {exc}"
        )
        return 2
    if not args.include_reported:
        findings = [item for item in findings if not state.was_reported(item.thread_key, item.message_id)]

    subject, body = render_email(findings, datetime.now(), config)

    if args.dry_run:
        print(f"Subject: {subject}\n")
        print(body)
        return 0

    send_email(subject, body, config)
    for item in findings:
        state.mark_reported(item.thread_key, item.message_id)
    return 0


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if __name__ == "__main__":
    raise SystemExit(main())
