from webapp2 import WSGIApplication
from google.appengine.api import wrap_wsgi_app

from mail import SendMail

app = WSGIApplication(
    [
        ("/", SendMail),
    ],
    debug=True,
)

app = wrap_wsgi_app(app)
