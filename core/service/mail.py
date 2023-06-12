import email
import imaplib
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import nextcord

from core import files, log, magic


def __valid_str__(text: str) -> bool:
    return text is not None and len(text) > 0


def __get_name__(body: str) -> Optional[str]:
    first_comma = body.find(", ")
    if first_comma == -1:
        return None
    first_comma += 2

    first_space_after_name = body.find(" ", first_comma)
    if first_space_after_name == -1:
        return None

    return body[first_comma:first_space_after_name]


def __get_message__(body: str) -> Optional[str]:
    separation = "\n----------------------------------------------------------------------\n"
    message_from = body.find(separation)
    if message_from == -1:
        return None

    message_from += len(separation)
    message_to = body.find(separation, message_from)
    if message_to == -1:
        return None

    return body[message_from:message_to]


class MailService:
    def __init__(self, config: files.EmailService):
        self.config = config

        if not self.__has_valid_credentials__():
            log.error("Some of the mail service credentials are not valid! Please double check.")

        self.email_plain = files.read_file("email.plain")
        self.email_html = files.read_file("email.html")

        if not __valid_str__(self.email_plain):
            log.error("Cannot find a valid 'email.plain' file in the root directory. Please check!")
        if not __valid_str__(self.email_html):
            log.error("Cannot find a valid 'email.html' file in the root directory. Please check!")

    def is_ready(self) -> bool:
        return self.__has_valid_credentials__() \
               and __valid_str__(self.email_plain) \
               and __valid_str__(self.email_html)

    def __has_valid_credentials__(self) -> bool:
        return __valid_str__(self.config.email()) \
               and __valid_str__(self.config.password()) \
               and __valid_str__(self.config.host()) \
               and self.config.port() > 0

    def send_formatted_mail(self, user: nextcord.Member, sender: str, spigot_name: str, promotion_key: int):
        email_content_html, email_content_plain = self.format_email(f"{user}", spigot_name, str(promotion_key))
        self.__send_email__(
            self.config.subject(),
            self.config.sender_name(),
            sender, sender,
            email_content_html,
            email_content_plain
        )

    def __send_email__(self, subject: str, sender_name: str, receiver_name: str, receiver_email: str, email_html: str,
                       email_plain: str):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_name
        msg['To'] = receiver_name
        msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")  # Tue, 18 Jan 2022 17:28:31 -0800

        msg.attach(MIMEText(email_plain, "plain"))
        msg.attach(MIMEText(email_html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host=self.config.host(), port=self.config.port(), context=context) as server:
            server.login(self.config.email(), self.config.password())
            server.sendmail(msg["From"], receiver_email, msg.as_string())

    def format_email(self, discord_user: str, spigot_user: str, promotion_key: str) -> (str, str):
        html = self.email_html.format(
            discord_user=discord_user,
            spigot_user=spigot_user,
            promotion_key=promotion_key
        )
        plain = self.email_plain.format(
            discord_user=discord_user,
            spigot_user=spigot_user,
            promotion_key=promotion_key
        )
        return html, plain

    def got_received_promotion_keys(self) -> dict[str, tuple[str, datetime]]:
        inbox = {}

        for mail in self.__fetch_multipart_mails__(2):
            sender, subject, date, body = mail

            if sender != "Spigot Forums <forums@spigotmc.org>":
                continue

            if "started a conversation with you" not in subject \
                    and "New reply to your conversation" not in subject:
                continue

            name = __get_name__(body)
            if name is None:
                continue

            message = __get_message__(body)
            if message is None:
                continue

            inbox[name.lower()] = (message, date)
        return inbox

    def __fetch_multipart_mails__(self, mail_count: int) \
            -> list[tuple[str, str, datetime, str]]:
        imap = imaplib.IMAP4_SSL(self.config.host())
        imap.login(self.config.email(), self.config.password())
        status, messages = imap.select("INBOX")

        if status != "OK":
            return []

        inbox = []
        messages = int(messages[0])
        mail_count = min(messages, mail_count)
        for i in range(messages - mail_count + 1, messages + 1, 1):
            res, msg = imap.fetch(str(i), "(RFC822)")

            for response in msg:
                if isinstance(response, tuple):
                    message = email.message_from_bytes(response[1])

                    sender = message.get("From")
                    subject = message["Subject"]

                    date_info: str = message["Date"]

                    # date info sometimes contains a '(CEST)'
                    idx = date_info.rfind(" (")
                    if idx != -1:
                        date_info = date_info[:idx]

                    try:
                        date = datetime.strptime(date_info, "%a, %d %b %Y %H:%M:%S %z").astimezone().replace(tzinfo=None)
                    except ValueError:
                        date = datetime.strptime(date_info, "%a, %d %b %Y %H:%M:%S %Z").astimezone().replace(tzinfo=None)

                    if message.is_multipart():
                        for part in message.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition"))

                            if content_type == "text/plain" and "attachment" not in content_disposition:
                                body = part.get_payload(decode=True).decode()
                                inbox.append((sender, subject, date, body))
        imap.close()
        imap.logout()
        return inbox
