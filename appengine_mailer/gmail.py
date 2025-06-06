#!/usr/bin/env python

import base64
import email.message
import email.parser
import hashlib
import hmac
import logging
import optparse  # pylint: disable=deprecated-module
import os
import sys
import requests
from google.cloud.secretmanager_v1 import SecretManagerServiceClient
from google.cloud.secretmanager_v1.types import AccessSecretVersionRequest

GMAIL_SECRET_NAME = (
    f"projects/{os.environ['GOOGLE_CLOUD_PROJECT']}/"
    f"secrets/{os.environ['GMAIL_SECRET_NAME']}/versions/latest"
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class MessageSendingFailure(Exception):
    pass


class Signer(object):
    def __init__(self):
        self.secret_key = (
            SecretManagerServiceClient()
            .access_secret_version(AccessSecretVersionRequest(name=GMAIL_SECRET_NAME))
            .payload.data.decode()
        )

    def sign(self, msg: str):
        signature = base64.encodebytes(
            hmac.new(
                bytes(self.secret_key, "utf-8"), bytes(msg, "utf-8"), hashlib.sha1
            ).digest()
        ).strip()
        log.debug(f"message: '{msg}'")
        log.debug(f"signature: '{signature!r}'")
        return signature

    def verify_signature(self, msg: str, signature: str):
        return self.sign(msg) == bytes(signature, "utf-8")


class Connection(object):
    def __init__(self, EMAIL_APPENGINE_PROXY_URL=None):
        if not EMAIL_APPENGINE_PROXY_URL:
            try:
                EMAIL_APPENGINE_PROXY_URL = os.environ["GMAIL_PROXY_URL"]
            except KeyError:
                try:
                    EMAIL_APPENGINE_PROXY_URL = (
                        open("/etc/envdir/GMAIL_PROXY_URL").readline().rstrip()
                    )
                except OSError:
                    raise EnvironmentError("GMAIL_PROXY_URL is not set.")
        self.EMAIL_APPENGINE_PROXY_URL = EMAIL_APPENGINE_PROXY_URL

    def make_request(self, data):
        response = requests.post(self.EMAIL_APPENGINE_PROXY_URL, data)
        return response.status_code, response.text


class GmailProxy(object):
    def __init__(
        self,
        EMAIL_APPENGINE_PROXY_URL=None,
        fix_sender=False,
        fail_silently=False,
    ):
        self.signer = Signer()
        self.connection = Connection(EMAIL_APPENGINE_PROXY_URL)
        self.fix_sender = fix_sender
        self.fail_silently = fail_silently

    def send_mail(self, msg):
        values = {
            "msg": msg.as_string(),
            "signature": self.signer.sign(msg.as_string()),
        }
        if self.fix_sender:
            values["fix_sender"] = "true"
        status, errmsg = self.connection.make_request(values)

        if status != 204 and not self.fail_silently:
            raise MessageSendingFailure(errmsg)


if __name__ == "__main__":
    """mail -s [space-separated to-addresses] to-address
    and the message on stdin"""
    parser = optparse.OptionParser()
    parser.add_option("-s", dest="subject", help="subject of message")
    parser.add_option(
        "--fix-sender",
        action="store_true",
        dest="fix_sender",
        help="If sender is not authorized, replace From with an authorized sender",
    )
    options, to_addresses = parser.parse_args()
    if to_addresses:
        msg = email.message.Message()
        msg["From"] = os.environ["USER"]
        msg["To"] = ",".join(to_addresses)  # escaping necessary?
        msg["Subject"] = options.subject
        msg.set_payload(sys.stdin.read())
    else:
        # We're expecting a whole message on stdin:
        msg = email.parser.Parser().parse(sys.stdin)
        recipient = os.environ.get("RECIPIENT")
        if recipient:
            msg["To"] = recipient
    GmailProxy(fix_sender=options.fix_sender).send_mail(msg)
