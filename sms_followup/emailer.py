from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

from .config import Config


def send_email(subject: str, body: str, config: Config) -> None:
    password = os.environ.get(config.email.smtp_password_env)
    if not password:
        raise RuntimeError(f"Missing SMTP password environment variable: {config.email.smtp_password_env}")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.email.from_address
    message["To"] = config.email.to_address
    message.set_content(body)

    with smtplib.SMTP(config.email.smtp_host, config.email.smtp_port) as smtp:
        smtp.starttls()
        smtp.login(config.email.smtp_username, password)
        smtp.send_message(message)
