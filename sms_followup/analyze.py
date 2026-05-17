from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime

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
    if config.use_ai and os.environ.get(config.openrouter_api_key_env):
        print(f"OpenRouter enabled; reviewing {len(threads)} thread(s) with {config.openrouter_model}.")
        findings = [_ai_based(thread, config) for thread in threads]
    else:
        if config.use_ai:
            print(f"AI enabled, but {config.openrouter_api_key_env} is not set; using rule-based fallback.")
        findings = [_rule_based(thread, config) for thread in threads]

    findings = [item for item in findings if item is not None]
    findings.sort(key=lambda item: (item.urgency != "high", item.last_message_at))
    return findings[: config.max_threads]


def _rule_based(thread: Thread, config: Config) -> Finding | None:
    messages = [msg for msg in thread.messages if _is_meaningful(msg)]
    if not messages:
        return None

    last = messages[-1]
    age_hours = _age_hours(last)
    if age_hours < config.minimum_age_hours:
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


def _ai_based(thread: Thread, config: Config) -> Finding | None:
    messages = [msg for msg in thread.messages if _is_meaningful(msg)]
    if not messages:
        return None

    last = messages[-1]
    decision = _classify_thread_with_openrouter(thread, messages, config)
    if decision.get("_error"):
        return _rule_based(thread, config)
    if not decision.get("include", False):
        return None

    message_id = _decision_message_id(decision, messages)
    message = next((msg for msg in messages if msg.message_id == message_id), last)
    urgency = str(decision.get("urgency") or "normal").lower()
    if urgency not in {"low", "normal", "high"}:
        urgency = "normal"

    return _finding(
        thread,
        message,
        str(decision.get("reason") or "The conversation appears to need attention."),
        str(decision.get("suggested_action") or "Review the thread and decide what to do next."),
        urgency,
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


def _classify_thread_with_openrouter(thread: Thread, messages: list[Message], config: Config) -> dict:
    transcript = "\n".join(
        f"[{msg.message_id}] {msg.date:%Y-%m-%d %H:%M} {'Me' if msg.is_from_me else msg.sender}: {msg.text}"
        for msg in messages[-20:]
    )
    last = messages[-1]
    payload = {
        "model": config.openrouter_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You analyze SMS/iMessage conversations for a daily follow-up digest. "
                    "Decide whether this thread currently needs action from Me. Include threads with "
                    "unanswered direct questions, requests, scheduling/logistics that need confirmation, "
                    "or commitments Me made that still appear open. Exclude casual concluded exchanges, "
                    "FYIs, acknowledgments, spam-like messages, and conversations where the other person "
                    "has already acknowledged or resolved the item. Return only JSON."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Contact/thread: {thread.display_name}\n"
                    f"Latest meaningful message age: {_age_hours(last):.1f} hours\n"
                    f"Configured minimum age for reminders: {config.minimum_age_hours} hours\n\n"
                    "Return a JSON object with these keys:\n"
                    "- include: boolean\n"
                    "- reason: short string\n"
                    "- suggested_action: short string\n"
                    "- urgency: one of low, normal, high\n"
                    "- message_id: integer id of the message most responsible for the decision\n\n"
                    f"Transcript:\n{transcript}"
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        config.openrouter_endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {os.environ[config.openrouter_api_key_env]}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/indianagreg/sms",
            "X-Title": "SMS Follow-Up Digest",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return _parse_model_json(_extract_chat_content(data))
    except Exception:
        return {"_error": "openrouter_request_failed"}


def _age_hours(message: Message) -> float:
    return (datetime.now() - message.date).total_seconds() / 3600


def _decision_message_id(decision: dict, messages: list[Message]) -> int:
    try:
        return int(decision.get("message_id"))
    except (TypeError, ValueError):
        return messages[-1].message_id


def _extract_chat_content(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        return "{}"
    message = choices[0].get("message") or {}
    content = message.get("content") or "{}"
    if isinstance(content, list):
        return "".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return str(content)


def _parse_model_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_error": "invalid_model_json"}
