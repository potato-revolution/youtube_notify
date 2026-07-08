"""Gmail SMTP(アプリパスワード)による HTML メール送信。失敗時は例外を伝播する。"""

import smtplib
import ssl
from email.mime.text import MIMEText

from app import config


class MailSender:
    def __init__(self, address: str | None = None, password: str | None = None) -> None:
        self._address = address or config.gmail_address()
        self._password = password or config.gmail_app_password()

    def send(self, subject: str, html_body: str) -> None:
        msg = MIMEText(html_body, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = self._address
        msg["To"] = self._address

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context) as smtp:
            smtp.login(self._address, self._password)
            smtp.send_message(msg)
