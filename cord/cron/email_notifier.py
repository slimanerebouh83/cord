"""
CORD Cron - Automated Email Dispatcher & Notification Engine
Supports SMTP delivery, attachment embedding (Word docx, PDFs, markdown), and offline outbox queuing.
"""

from __future__ import annotations
import email
import json
import os
import smtplib
import time
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Dict, List, Optional, Any


class EmailNotifier:
    """Dispatches scheduled automated emails with optional attachments."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            self.config_path = Path.home() / ".cord" / "email.json"
        else:
            self.config_path = config_path

        self.outbox_dir = Path.home() / ".cord" / "outbox"
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self._load_config()

    def _load_config(self) -> None:
        self.smtp_host = os.environ.get("SMTP_HOST", "")
        self.smtp_port = int(os.environ.get("SMTP_PORT", 587))
        self.smtp_user = os.environ.get("SMTP_USER", "")
        self.smtp_password = os.environ.get("SMTP_PASSWORD", "")
        self.from_email = os.environ.get("FROM_EMAIL", self.smtp_user or "cord-agent@noreply.local")

        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self.smtp_host = data.get("smtp_host", self.smtp_host)
                self.smtp_port = int(data.get("smtp_port", self.smtp_port))
                self.smtp_user = data.get("smtp_user", self.smtp_user)
                self.smtp_password = data.get("smtp_password", self.smtp_password)
                self.from_email = data.get("from_email", self.from_email or self.smtp_user)
            except Exception:
                pass

    def save_config(self, host: str, port: int, user: str, password: str, from_email: Optional[str] = None) -> None:
        self.smtp_host = host
        self.smtp_port = port
        self.smtp_user = user
        self.smtp_password = password
        self.from_email = from_email or user

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps({
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_user": self.smtp_user,
            "smtp_password": self.smtp_password,
            "from_email": self.from_email,
        }, indent=2), encoding="utf-8")

    def send(
        self,
        to_email: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        attachments: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Sends an email via SMTP or stores in outbox if SMTP is not configured.
        """
        self._load_config()
        clean_to = to_email.strip()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_email
        msg["To"] = clean_to

        # Attach text and html parts
        part1 = MIMEText(body_text, "plain", "utf-8")
        msg.attach(part1)
        if body_html:
            part2 = MIMEText(body_html, "html", "utf-8")
            msg.attach(part2)

        # Attach files (e.g. Word .docx, markdown, log files)
        valid_attachments = []
        if attachments:
            for fpath in attachments:
                p = Path(fpath).expanduser().resolve()
                if p.exists() and p.is_file():
                    valid_attachments.append(str(p))
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(p.read_bytes())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={p.name}",
                    )
                    msg.attach(part)

        # If SMTP is configured, attempt live dispatch
        if self.smtp_host and self.smtp_user and self.smtp_password:
            try:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=15)
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, [clean_to], msg.as_string())
                server.quit()
                return {
                    "success": True,
                    "mode": "live_smtp",
                    "recipient": clean_to,
                    "subject": subject,
                    "attachments": valid_attachments,
                    "message": f"Email successfully dispatched to {clean_to} via {self.smtp_host}:{self.smtp_port}",
                }
            except Exception as e:
                # Fallback to outbox on connection error
                outbox_file = self._save_to_outbox(clean_to, subject, body_text, valid_attachments)
                return {
                    "success": True,
                    "mode": "outbox_fallback",
                    "recipient": clean_to,
                    "subject": subject,
                    "outbox_path": str(outbox_file),
                    "warning": f"SMTP dispatch failed ({e}). Saved email to outbox queue.",
                }
        else:
            # Save to outbox
            outbox_file = self._save_to_outbox(clean_to, subject, body_text, valid_attachments)
            return {
                "success": True,
                "mode": "outbox_queued",
                "recipient": clean_to,
                "subject": subject,
                "outbox_path": str(outbox_file),
                "message": (
                    f"Email queued to {outbox_file.name}. "
                    f"To enable live SMTP sending, configure ~/.cord/email.json with your SMTP credentials."
                ),
            }

    def _save_to_outbox(self, to: str, subject: str, body: str, attachments: List[str]) -> Path:
        safe_subj = "".join(c if c.isalnum() else "_" for c in subject)[:30]
        out_file = self.outbox_dir / f"{int(time.time())}_{safe_subj}.json"
        out_file.write_text(json.dumps({
            "to": to,
            "subject": subject,
            "body": body,
            "attachments": attachments,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2), encoding="utf-8")
        return out_file


email_notifier = EmailNotifier()
