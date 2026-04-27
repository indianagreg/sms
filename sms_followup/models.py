from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Message:
    message_id: int
    date: datetime
    is_from_me: bool
    sender: str
    text: str


@dataclass(frozen=True)
class Thread:
    thread_key: str
    display_name: str
    participants: tuple[str, ...]
    messages: tuple[Message, ...]


@dataclass(frozen=True)
class Finding:
    thread_key: str
    message_id: int
    display_name: str
    reason: str
    suggested_action: str
    urgency: str
    last_message_at: datetime
    excerpt: str
