from email.message import Message
import email.parser
import email.utils
import logging
import os
from gmail import Signer
from google.appengine.api.mail import (  # type:ignore[import-untyped]
    EmailMessage,
)
from google.appengine.api.mail_errors import InvalidSenderError
from webapp2 import RequestHandler  # type:ignore[import-untyped]
from webob import exc

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


DEFAULT_SENDER_DOMAIN = f"{os.environ['GOOGLE_CLOUD_PROJECT']}.appspotmail.com"
DEFAULT_SENDER = "noreply@" + DEFAULT_SENDER_DOMAIN


class BadRequestError(exc.HTTPBadRequest):
    def __init__(self, message):
        super(BadRequestError, self).__init__("Malformed request: " + message)


class BadMessageError(exc.HTTPBadRequest):
    def __init__(self, message):
        super(BadMessageError, self).__init__("Failed to send message: " + message)


class SendMail(RequestHandler):
    def __init__(self, *args, **kwargs):
        super(SendMail, self).__init__(*args, **kwargs)
        self.signer = Signer()

    def get(self):
        # Just so that we can pingdom it to see if it's up.
        return

    def post(self):
        msg_string, fix_sender = self.parse_args()
        msg: Message = email.parser.Parser().parsestr(msg_string)

        api_msg = self.translate_message(msg, fix_sender)
        api_msg.check_initialized()
        try:
            api_msg.send()
        except InvalidSenderError:
            if fix_sender:
                log.warning("Invalid sender, fixing to %s", DEFAULT_SENDER)
                api_msg.sender = DEFAULT_SENDER
                api_msg.send()
            else:
                raise
        log.info("Sent message ok")
        log.debug("Sent message: %s", msg)

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
        return self.signer.verify_signature(msg, signature)

    def translate_message(self, msg: Message, fix_sender: bool = False) -> EmailMessage:
        sender = msg["From"]
        if not sender:
            if fix_sender:
                msg["From"] = DEFAULT_SENDER
            else:
                raise BadMessageError("No sender specified")
        else:
            realname, address = email.utils.parseaddr(sender)
            if "@" not in address:
                sender_address = address
                sender_domain = DEFAULT_SENDER_DOMAIN
            else:
                sender_address, sender_domain = address.split("@", 1)
                if sender_domain.endswith("local"):
                    sender_domain = DEFAULT_SENDER_DOMAIN
            sender = email.utils.formataddr(
                (realname, sender_address + "@" + sender_domain)
            )
        log.info("Using sender: %s", sender)
        message = EmailMessage(sender=sender, mime_message=msg)

        return message
