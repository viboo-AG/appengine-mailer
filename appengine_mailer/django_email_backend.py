from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

from gmail import GmailProxy, MessageSendingFailure

EMAIL_OVERRIDE = getattr(settings, 'EMAIL_OVERRIDE', None)

class GmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, *args, **kwargs):
        self.gmail_proxy = GmailProxy(settings.SECRET_KEY, settings.EMAIL_APPENGINE_PROXY_URL, fail_silently)
        super(GmailBackend, self).__init__(fail_silently, *args, **kwargs)

    def send_messages(self, messages):
        n = 0
        for message in messages:
            if settings.DEBUG and EMAIL_OVERRIDE:
                message.to = EMAIL_OVERRIDE
            try:
                self.gmail_proxy.send_mail(message.message())
                n += 1
            except MessageSendingFailure:
                pass
        return n
