"""Minimal email delivery: a development file sink and SMTP (stdlib only).

Logging rule: never log message bodies (they contain reset links) or SMTP
credentials. Only recipients' domains and file paths are logged.
"""

import logging
import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Protocol

from app.core.config import Settings

log = logging.getLogger("opencampus.email")


class EmailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


def _message(settings: Settings, to: str, subject: str, body: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = settings.email_from
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain="opencampus.local")
    message.set_content(body, cte="7bit")  # plain ASCII: links stay copyable in raw .eml files
    return message


def _domain(address: str) -> str:
    return address.rsplit("@", 1)[-1]


class DevFileSender:
    """Writes each email as an .eml file instead of sending it. Refused by
    configuration when OPENCAMPUS_ENV=production."""

    def __init__(self, settings: Settings):
        self._settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        directory = self._settings.email_dev_dir
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        path = directory / f"{stamp}-{uuid.uuid4().hex[:8]}.eml"
        path.write_bytes(bytes(_message(self._settings, to, subject, body)))
        log.info("Development email for *@%s written to %s", _domain(to), path)


class SmtpSender:
    def __init__(self, settings: Settings):
        self._settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        s = self._settings
        message = _message(s, to, subject, body)
        context = ssl.create_default_context()  # verifies certificates and hostnames
        if s.smtp_tls == "ssl":
            client: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15, context=context)
        else:
            client = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
        with client:
            client.ehlo()
            if s.smtp_tls == "starttls":
                client.starttls(context=context)
                client.ehlo()
            if s.smtp_username:
                client.login(s.smtp_username, s.smtp_password)
            client.send_message(message)
        log.info("Email for *@%s sent via SMTP", _domain(to))


def get_email_sender(settings: Settings) -> EmailSender:
    return SmtpSender(settings) if settings.email_mode == "smtp" else DevFileSender(settings)
