import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from core import files, log


def __valid_str__(text: str) -> bool:
    return text is not None and len(text) > 0


class MailService:
    def __init__(self, config: files.EmailService):
        self.email = config.email()
        self.password = config.password()
        self.host = config.host()
        self.port = config.port()

        if not self.has_valid_credentials():
            log.error("Some of the mail service credentials are not valid! Please double check.")

    def has_valid_credentials(self):
        return __valid_str__(self.email) \
               and __valid_str__(self.password) \
               and __valid_str__(self.host) \
               and self.port is not None and self.port > 0

    def send_email(self, subject: str, sender_name: str, receiver_name: str, receiver_email: str, email_html: str,
                   email_plain: str):
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender_name
        msg['To'] = receiver_name
        msg['Date'] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")  # Tue, 18 Jan 2022 17:28:31 -0800

        msg.attach(MIMEText(email_plain, "plain"))
        msg.attach(MIMEText(email_html, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host=self.host, port=self.port, context=context) as server:
            server.login(self.email, self.password)
            server.sendmail(msg["From"], receiver_email, msg.as_string())
