from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta

from .config import Config
from .models import Finding, Message, Thread

ACTION_PATTERNS = re.compile(
    r"\?|can you|could you|would you|please|let me know|send me|remind me|"
    r"are we|do you|did you|will you|when|where|what time|call me|text me|"
    r"follow up|book|schedule|confirm|need",
    re.IGNORECASE,
)

COMMITMENT_PATTERNS = re.compile(
    r"\b(i'll|i will|i can|i should|i need to|let me|i'm going to|"
    r"i am going to|will send|will call|will check)\b",
    re.IGNORECASE,
)

LOW_SIGNAL = {
    "ok",
    "okay",
    "k",
    "kk",
    "thanks",
    "thank you",
    "thx",
    "sounds good",
    "sg",
    "👍",
}


def analyze_threads(threads: list[Thread], config: Config) -> list[Finding]:
    findings = [_rule_based(thread, config) for thread in threads]
    findings = [item for item in findings if item is not None]
    findings.sort(key=lambda item: (item.urgency != "high", item.last_message_at))
    findings = findings[: config.max_threads]

    if config.use_openai and os.environ.get("OPENAI_API_KEY"):
        return _refine_with_openai(findings, threads, config)
    return findings


def _rule_based(thread: Thread, config: Config) -> Finding | None:
    messages = [msg for msg in thread.messages if _is_meaningful(msg)]
    if not messages:
        return None

    last = messages[-1]
    now = datetime.now()
    if now - last.date < timedelta(hours=config.minimum_age_hours):
        return None

    if not last.is_from_me:
        reason = "Last meaningful message was inbound and has not been answered."
        action = "Reply or decide that no response is needed."
        urgency = "high" if ACTION_PATTERNS.search(last.text) else "normal"
        return _finding(thread, last, reason, action, urgency)

    recent_outbound_commitment = _last_outbound_commitment(messages)
    if recent_outbound_commitment and not _has_later_inbound_ack(messages, recent_outbound_commitment):
        return _finding(
            thread,
            recent_outbound_commitment,
            "You appear to have made a commitment that may still need completion.",
            "Complete the promised action or send an update.",
            "normal",
        )

    return None


def _finding(thread: Thread, message: Message, reason: str, action: str, urgency: str) -> Finding:
    return Finding(
        thread_key=thread.thread_key,
        message_id=message.message_id,
        display_name=thread.display_name,
        reason=reason,
        suggested_action=action,
        urgency=urgency,
        last_message_at=message.date,
        excerpt=message.text[:280],
    )


def _is_meaningful(message: Message) -> bool:
    normalized = message.text.strip().lower()
    return bool(normalized) and normalized not in LOW_SIGNAL


def _last_outbound_commitment(messages: list[Message]) -> Message | None:
    for message in reversed(messages):
        if message.is_from_me and COMMITMENT_PATTERNS.search(message.text):
            return message
    return None


def _has_later_inbound_ack(messages: list[Message], commitment: Message) -> bool:
    later = [msg for msg in messages if msg.date > commitment.date and not msg.is_from_me]
    return any(msg.text.strip().lower() in LOW_SIGNAL for msg in later)


def _refine_with_openai(findings: list[Finding], threads: list[Thread], config: Config) -> list[Finding]:
    thread_by_key = {thread.thread_key: thread for thread in threads}
    refined: list[Finding] = []
    for finding in findings:
        thread = thread_by_key.get(finding.thread_key)
        if thread is None:
            refined.append(finding)
            continue
        decision = _classify_thread_with_openai(thread, finding, config)
        if decision.get("include", True):
            refined.append(
                Finding(
                    thread_key=finding.thread_key,
                    message_id=finding.message_id,
                    display_name=finding.display_name,
                    reason=str(decision.get("reason") or finding.reason),
                    suggested_action=str(decision.get("suggested_action") or finding.suggested_action),
                    urgency=str(decision.get("urgency") or finding.urgency),
                    last_message_at=finding.last_message_at,
                    excerpt=finding.excerpt,
                )
            )
    return refined


def _classify_thread_with_openai(thread: Thread, finding: Finding, config: Config) -> dict:
    transcript = "\n".join(
        f"{msg.date:%Y-%m-%d %H:%M} {'Me' if msg.is_from_me else msg.sender}: {msg.text}"
        for msg in thread.messages[-20:]
    )
    payload = {
        "model": config.openai_model,
        "input": [
            {
                "role": "system",
                "content": (
                    "Decide whether this SMS/iMessage thread still needs action from Me. "
                    "Return only compact JSON with include boolean, reason, suggested_action, urgency."
                ),
            },
            {
                "role": "user",
                "content": f"Initial reason: {finding.reason}\n\nTranscript:\n{transcript}",
            },
        ],
        "text": {"format": {"type": "json_object"}},
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        text = data.get("output_text") or _extract_output_text(data)
        return json.loads(text)
    except Exception:
        return {"include": True}


def _extract_output_text(data: dict) -> str:
    parts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if "text" in content:
                parts.append(content["text"])
    return "".join(parts)
