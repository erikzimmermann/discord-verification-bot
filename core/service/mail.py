import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import nextcord

from core import files, log


def __valid_str__(text: str) -> bool:
    return text is not None and len(text) > 0


class MailService:
    def __init__(self, config: files.EmailService):
        self.config = config

        if not self.is_ready():
            log.error("Some of the mail service credentials are not valid! Please double check.")

        self.email_html = files.read_file("email.html")
        self.email_plain = files.read_file("email.plain")
        if not self.email_html:
            log.error("Cannot find a valid 'email.html' file in the root directory. Please check!")
        if not self.email_plain:
            log.error("Cannot find a valid 'email.plain' file in the root directory. Please check!")

    def is_ready(self):
        return self.__has_valid_credentials__() and self.email_plain and self.email_html

    def __has_valid_credentials__(self):
        return __valid_str__(self.config.email()) \
               and __valid_str__(self.config.password()) \
               and __valid_str__(self.config.host()) \
               and self.config.port() > 0

    def send_formatted_mail(self, user: nextcord.Member, email: str, spigot_name: str, promotion_key: int):
        email_content_html, email_content_plain = self.format_email(f"{user}", spigot_name, str(promotion_key))
        self.__send_email__(
            self.config.subject(),
            self.config.sender_name(),
            email, email,
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
