from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_PATH = "~/.sms-followup/config.json"
DEFAULT_STATE_PATH = "~/.sms-followup/state.sqlite"


@dataclass(frozen=True)
class EmailConfig:
    smtp_host: str
    smtp_port: int
    smtp_use_ssl: bool
    smtp_username: str
    smtp_password_env: str
    from_address: str
    to_address: str
    subject_prefix: str = "SMS follow-up"


@dataclass(frozen=True)
class Config:
    lookback_hours: int
    minimum_age_hours: int
    max_threads: int
    ignore_contacts: frozenset[str]
    ignore_group_chats: bool
    resolve_contacts: bool
    use_ai: bool
    openrouter_model: str
    openrouter_api_key_env: str
    openrouter_endpoint: str
    email: EmailConfig
    messages_db_path: str = "~/Library/Messages/chat.db"
    contacts_db_glob: str = "~/Library/Application Support/AddressBook/Sources/*/AddressBook-v*.abcddb"
    state_path: str = DEFAULT_STATE_PATH


def load_config(path: Path) -> Config:
    path = path.expanduser()
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    email = raw.get("email", {})
    state_path = _resolve_path(str(raw.get("state_path", DEFAULT_STATE_PATH)), path.parent)
    return Config(
        lookback_hours=int(raw.get("lookback_hours", 72)),
        minimum_age_hours=int(raw.get("minimum_age_hours", 4)),
        max_threads=int(raw.get("max_threads", 30)),
        ignore_contacts=frozenset(raw.get("ignore_contacts", [])),
        ignore_group_chats=bool(raw.get("ignore_group_chats", False)),
        resolve_contacts=bool(raw.get("resolve_contacts", True)),
        use_ai=bool(raw.get("use_ai", raw.get("use_openrouter", raw.get("use_openai", False)))),
        openrouter_model=str(raw.get("openrouter_model", raw.get("openai_model", "openai/gpt-4.1-mini"))),
        openrouter_api_key_env=str(raw.get("openrouter_api_key_env", "OPENROUTER_API_KEY")),
        openrouter_endpoint=str(raw.get("openrouter_endpoint", "https://openrouter.ai/api/v1/chat/completions")),
        messages_db_path=str(raw.get("messages_db_path", "~/Library/Messages/chat.db")),
        contacts_db_glob=str(
            raw.get("contacts_db_glob", "~/Library/Application Support/AddressBook/Sources/*/AddressBook-v*.abcddb")
        ),
        state_path=state_path,
        email=EmailConfig(
            smtp_host=str(email["smtp_host"]),
            smtp_port=int(email.get("smtp_port", 587)),
            smtp_use_ssl=bool(email.get("smtp_use_ssl", int(email.get("smtp_port", 587)) == 465)),
            smtp_username=str(email["smtp_username"]),
            smtp_password_env=str(email.get("smtp_password_env", "SMS_FOLLOWUP_SMTP_PASSWORD")),
            from_address=str(email["from_address"]),
            to_address=str(email["to_address"]),
            subject_prefix=str(email.get("subject_prefix", "SMS follow-up")),
        ),
    )


def _resolve_path(value: str, base_dir: Path) -> str:
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    return str(base_dir / path)
