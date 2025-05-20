# Adaptation of appengine-mailer

This repo has been forked from the [original appengine-mailer repo](https://github.com/mixcloud/appengine-mailer) by Toby White.

See the original README for more detailed information.

Summary of changes from the upstream version:

* Adapt to 2nd generation App Engine runtime
* Adapt to Python 3
* Replace deprecated APIs with current ones
* Remove non-essential files and functionality
* Get the signature key from a GCP secret whose name is passed in the `GMAIL_SECRET_NAME` environment variable

## Deployment

From the root of the repo

```sh
gcloud app deploy appengine_mailer/
```

will deploy to the current GCP project set by `gcloud config set project`.
