from email.message import Message
import email.parser
import logging
import os
from gmail import Signer
from google.appengine.api.mail import (  # type:ignore[import-untyped]
    EmailMessage,
    InvalidSenderError,
)
from google.cloud.secretmanager_v1 import SecretManagerServiceClient
from google.cloud.secretmanager_v1.types import AccessSecretVersionRequest

from webapp2 import RequestHandler  # type:ignore[import-untyped]

GMAIL_SECRET_NAME = (
    f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/"
    f"secrets/{os.environ['GMAIL_SECRET_NAME']}/versions/latest"
)

DEFAULT_SENDER = f"noreply@{os.environ['GOOGLE_CLOUD_PROJECT']}.appspotmail.com"

suffixes = dict(
    line.split()[:2]
    for line in open("google.mime.types", encoding="utf-8")
    if not line.startswith("#")
)


class BadRequestError(ValueError):
    pass


class BadMessageError(ValueError):
    pass


class Mailer(object):
    def __init__(self, default_sender=DEFAULT_SENDER, fix_sender=False):
        self.default_sender = default_sender
        self.fix_sender = fix_sender

    def send_message(self, msg: Message):
        message = self.translate_message(msg)
        try:
            message.send()
            return
        except InvalidSenderError as e:
            if not self.fix_sender:
                raise BadMessageError(
                    "Unauthorized message sender '%s'" % message.sender
                ) from e
        message.sender = self.default_sender
        try:
            message.send()
        except InvalidSenderError as e:
            raise BadMessageError(
                "Unauthorized default message sender '%s'" % message.sender
            ) from e

    @staticmethod
    def get_filename(part):
        filename = part.get_filename()
        if not filename:
            content_type = part.get_content_type()
            try:
                filename = "file.%s" % suffixes[content_type]
            except KeyError as e:
                raise BadMessageError(
                    "Google won't let us send content of type '%s'" % content_type
                ) from e
        return filename

    def translate_message(self, msg: Message):
        sender = msg["From"] or DEFAULT_SENDER
        if not sender:
            if self.fix_sender:
                sender = self.default_sender
            else:
                raise BadMessageError("No sender specified")
        to = msg["To"]
        if not to:
            raise BadMessageError("No destination addresses specified")
        message = EmailMessage(sender=sender or msg["From"], to=to)
        # Go through all the headers which Google will let us use
        cc = msg["Cc"]
        if cc:
            message.cc = cc
        bcc = msg["Bcc"]
        if bcc:
            message.bcc = cc
        reply_to = msg["Reply-To"]
        if reply_to:
            message.reply_to = reply_to
        subject = msg["Subject"]
        if subject:
            message.subject = subject

        # If there's just a plain text body, use that, otherwise
        # iterate over all the attachments
        payload = msg.get_payload(decode=True)
        if isinstance(payload, str):
            message.body = payload
        else:
            body = ""
            html = ""
            attachments = []
            # GAE demands we specify the body explicitly - we use the first text/plain attachment we find.
            # Similarly, we pull in the first html we find and use that for message.html
            # We pull in any other attachments we find; but we ignore the multipart structure,
            # because GAE doesn't give us enough control there.
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not body:
                    body = part.get_payload(decode=True)
                elif part.get_content_type() == "text/html" and not html:
                    html = part.get_payload(decode=True)
                elif not part.get_content_type().startswith("multipart"):
                    attachments.append(
                        (part.get_filename(), part.get_payload(decode=True))
                    )
            if not body:
                raise BadMessageError("No message body specified")
            message.body = body
            if html:
                message.html = html
            if attachments:
                message.attachments = attachments
        return message


class SendMail(RequestHandler):
    def __init__(self, *args, **kwargs):
        self.GMAIL_SECRET_KEYS = [
            SecretManagerServiceClient()
            .access_secret_version(AccessSecretVersionRequest(name=GMAIL_SECRET_NAME))
            .payload.data.decode()
        ]
        super(SendMail, self).__init__(*args, **kwargs)

    def get(self):
        # Just so that we can pingdom it to see if it's up.
        return

    def post(self):
        assert self.response
        try:
            msg_string, fix_sender = self.parse_args()
            msg: Message = email.parser.Parser().parsestr(msg_string)
            mailer = Mailer(fix_sender=fix_sender)
            mailer.send_message(msg)
            logging.info("Sent message ok\n%s", msg)
            self.error(204)
        except BadRequestError as e:
            logging.error("Malformed request: %s", e.args[0])
            self.error(400)
            self.response.out.write(e.args[0])
        except BadMessageError as e:
            logging.error("Failed to send message: %s", e.args[0])
            self.error(400)
            self.response.out.write(e.args[0])
        except Exception as e:
            logging.exception("Failed to process request")
            self.error(500)

    def parse_args(self):
        assert self.request
        msg = self.request.get("msg")
        if not msg:
            raise BadRequestError("No message found")
        signature = self.request.get("signature")
        if not signature:
            raise BadRequestError("No signature found")
        if not self.check_signature(msg, signature):
            raise BadRequestError("Signature doesn't match")
        fix_sender = bool(self.request.get("fix_sender"))
        return msg, fix_sender

    def check_signature(self, msg, signature: str):
        return Signer(self.GMAIL_SECRET_KEYS).verify_signature(msg, signature)
