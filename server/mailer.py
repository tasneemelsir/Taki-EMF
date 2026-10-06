"""
mailer.py
=========
Sends the few emails Taki needs (password-reset links) through any SMTP
service: a university or company mail server, Gmail with an app password,
Brevo, Mailgun, Resend ... Email is optional. Without it, a reset link is
printed in the server window for whoever runs the server to pass on.

    TAKI_SMTP_HOST       mail server, e.g. smtp.gmail.com     (unset = no email)
    TAKI_SMTP_PORT       587
    TAKI_SMTP_USER       sign-in name, usually the address
    TAKI_SMTP_PASSWORD   password or app password
    TAKI_SMTP_FROM       sender shown on the message          (TAKI_SMTP_USER)
    TAKI_SMTP_SECURITY   starttls | ssl | none                (starttls)
    TAKI_PUBLIC_URL      address people open Taki at, e.g. https://taki.example.org
                         (required for email: links are built from it, never from
                         the incoming request, which a stranger can forge)
"""

from __future__ import annotations

import smtplib
import ssl
import sys
import threading
from email.message import EmailMessage

from . import config


def configured() -> bool:
    return bool(config.SMTP_HOST and config.PUBLIC_URL)


def send(to: str, subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM or config.SMTP_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if config.SMTP_SECURITY == "ssl":
        server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20,
                                  context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
    with server:
        if config.SMTP_SECURITY == "starttls":
            server.starttls(context=ssl.create_default_context())
        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)


def send_async(to: str, subject: str, text: str) -> None:
    """Send in the background so the reply to the browser does not wait for the mail server."""
    def work():
        try:
            send(to, subject, text)
        except Exception as exc:                 # the visitor is told the same thing either way
            print(f"  Could not send email to {to}: {exc}", file=sys.stderr, flush=True)
    threading.Thread(target=work, daemon=True).start()
