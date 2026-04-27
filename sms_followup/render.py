from __future__ import annotations

from datetime import datetime

from .config import Config
from .models import Finding


def render_email(findings: list[Finding], now: datetime, config: Config) -> tuple[str, str]:
    subject = f"{config.email.subject_prefix}: {len(findings)} item(s) for {now:%b %-d}"
    if not findings:
        return subject, "No SMS follow-ups found for today.\n"

    lines = [
        f"SMS follow-up digest for {now:%A, %B %-d, %Y}",
        "",
        "Needs attention",
        "",
    ]
    for index, item in enumerate(findings, start=1):
        lines.extend(
            [
                f"{index}. {item.display_name} ({item.urgency})",
                f"   Last relevant message: {item.last_message_at:%Y-%m-%d %H:%M}",
                f"   Why: {item.reason}",
                f"   Suggested action: {item.suggested_action}",
                f"   Excerpt: {item.excerpt}",
                "",
            ]
        )
    return subject, "\n".join(lines)
