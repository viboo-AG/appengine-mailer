from webapp2 import WSGIApplication

from mail import SendMail

app = WSGIApplication(
    [
        ("/", SendMail),
    ],
    debug=True,
)


def main():
    app.run()


if __name__ == "__main__":
    main()
