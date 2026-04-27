from __future__ import annotations

import glob
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

from .config import Config


class ContactResolver:
    def __init__(self, names_by_phone: dict[str, str]) -> None:
        self.names_by_phone = names_by_phone

    @classmethod
    def from_config(cls, config: Config) -> "ContactResolver":
        if not config.resolve_contacts:
            return cls({})

        names: dict[str, str] = {}
        for db_path in _contact_databases(config.contacts_db_glob):
            try:
                names.update(_load_contact_names(db_path))
            except (OSError, PermissionError, sqlite3.Error):
                continue
        return cls(names)

    def display_name(self, handle: str | None) -> str | None:
        if not handle:
            return None
        phone_key = _phone_key(handle)
        if not phone_key:
            return None
        return self.names_by_phone.get(phone_key)


def _contact_databases(pattern: str) -> list[Path]:
    return [Path(path) for path in glob.glob(str(Path(pattern).expanduser()))]


def _load_contact_names(db_path: Path) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="sms-followup-contacts-") as temp_dir:
        copied_db = _copy_sqlite_database(db_path, Path(temp_dir))
        return _query_contact_names(copied_db)


def _query_contact_names(db_path: Path) -> dict[str, str]:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if not _has_tables(connection, {"ZABCDRECORD", "ZABCDPHONENUMBER"}):
            return {}

        record_columns = _columns(connection, "ZABCDRECORD")
        phone_columns = _columns(connection, "ZABCDPHONENUMBER")
        name_expr = _name_expression(record_columns)
        phone_expr = _phone_expression(phone_columns)
        if not name_expr or not phone_expr:
            return {}

        query = f"""
            SELECT {name_expr} AS contact_name, {phone_expr} AS phone_number
            FROM ZABCDPHONENUMBER phone
            JOIN ZABCDRECORD record ON record.Z_PK = phone.ZOWNER
        """
        names: dict[str, str] = {}
        for row in connection.execute(query):
            contact_name = " ".join(str(row["contact_name"] or "").split())
            phone_key = _phone_key(str(row["phone_number"] or ""))
            if contact_name and phone_key:
                names.setdefault(phone_key, contact_name)
        return names
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


def _has_tables(connection: sqlite3.Connection, names: set[str]) -> bool:
    found = {
        row["name"]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (%s)"
            % ",".join("?" for _ in names),
            tuple(names),
        )
    }
    return names.issubset(found)


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}


def _name_expression(columns: set[str]) -> str | None:
    candidates = [
        column
        for column in ("ZFIRSTNAME", "ZMIDDLENAME", "ZLASTNAME", "ZORGANIZATION", "ZNICKNAME")
        if column in columns
    ]
    if not candidates:
        return None
    parts = " || ' ' || ".join(f"COALESCE(record.{column}, '')" for column in candidates)
    return f"TRIM({parts})"


def _phone_expression(columns: set[str]) -> str | None:
    for column in ("ZFULLNUMBER", "ZNORMALIZEDNUMBER", "ZNUMBER"):
        if column in columns:
            return f"phone.{column}"
    return None


def _phone_key(value: str) -> str | None:
    digits = "".join(re.findall(r"\d+", value))
    if len(digits) < 7:
        return None
    return digits[-10:] if len(digits) >= 10 else digits
