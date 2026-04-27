from __future__ import annotations

import shutil
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config
from .contacts import ContactResolver
from .models import Message, Thread

MAC_EPOCH = datetime(2001, 1, 1)


def load_threads(config: Config) -> list[Thread]:
    db_path = Path(config.messages_db_path).expanduser()
    if not db_path.exists():
        raise FileNotFoundError(f"Messages database not found: {db_path}")

    with tempfile.TemporaryDirectory(prefix="sms-followup-") as temp_dir:
        copied_db = _copy_sqlite_database(db_path, Path(temp_dir))
        rows = _query_messages(copied_db, config.lookback_hours)

    grouped: dict[str, list[Message]] = defaultdict(list)
    names: dict[str, str] = {}
    participants: dict[str, set[str]] = defaultdict(set)
    contacts = ContactResolver.from_config(config)

    for row in rows:
        thread_key = str(row["chat_id"])
        text = _clean_text(row["text"])
        if not text:
            continue

        raw_sender = row["handle_id"] or "Unknown"
        contact_name = contacts.display_name(raw_sender)
        sender = "Me" if row["is_from_me"] else (contact_name or raw_sender)
        display_name = row["display_name"] or contact_name or row["chat_identifier"] or sender
        if sender in config.ignore_contacts or raw_sender in config.ignore_contacts or display_name in config.ignore_contacts:
            continue

        names[thread_key] = display_name
        if sender != "Me":
            participants[thread_key].add(sender)
        grouped[thread_key].append(
            Message(
                message_id=int(row["message_id"]),
                date=_from_mac_time(int(row["date"] or 0)),
                is_from_me=bool(row["is_from_me"]),
                sender=sender,
                text=text,
            )
        )

    threads = []
    for key, messages in grouped.items():
        if config.ignore_group_chats and len(participants[key]) > 1:
            continue
        threads.append(
            Thread(
                thread_key=key,
                display_name=names.get(key, key),
                participants=tuple(sorted(participants[key])),
                messages=tuple(sorted(messages, key=lambda msg: msg.date)),
            )
        )
    return threads


def _query_messages(db_path: Path, lookback_hours: int) -> list[sqlite3.Row]:
    since = _to_mac_time(datetime.now() - timedelta(hours=lookback_hours))
    query = """
        SELECT
            chat.ROWID AS chat_id,
            chat.display_name AS display_name,
            chat.chat_identifier AS chat_identifier,
            message.ROWID AS message_id,
            message.date AS date,
            message.is_from_me AS is_from_me,
            message.text AS text,
            handle.id AS handle_id
        FROM message
        JOIN chat_message_join ON chat_message_join.message_id = message.ROWID
        JOIN chat ON chat.ROWID = chat_message_join.chat_id
        LEFT JOIN handle ON handle.ROWID = message.handle_id
        WHERE message.date >= ?
        ORDER BY chat.ROWID, message.date
    """
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        return list(connection.execute(query, (since,)))
    finally:
        connection.close()


def _copy_sqlite_database(source: Path, target_dir: Path) -> Path:
    target = target_dir / source.name
    shutil.copy2(source, target)
    for suffix in ("-wal", "-shm"):
        sidecar = source.with_name(source.name + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, target.with_name(target.name + suffix))
    return target


def _from_mac_time(value: int) -> datetime:
    if value <= 0:
        return MAC_EPOCH
    return MAC_EPOCH + timedelta(seconds=value / 1_000_000_000)


def _to_mac_time(value: datetime) -> int:
    return int((value - MAC_EPOCH).total_seconds() * 1_000_000_000)


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.replace("\ufffc", " ").split())
