#!/bin/sh

test $# -lt 5 && echo "Usage: ${0} <project base name> <project count> <secret name> <billing account> <region>" && exit 1

set -e

SECRET_NAME=$3
BILLING_ACCOUNT=$4
REGION=$5

secret=$(gcloud secrets versions access --secret=${SECRET_NAME} latest)

for i in $(seq 1 $2); do
    PROJECT_NAME=$(printf "%s-%03d" "$1" "$i")
    service_account_name="serviceAccount:${PROJECT_NAME}@appspot.gserviceaccount.com"
    gcloud projects describe ${PROJECT_NAME} || gcloud projects create --labels=created_by=deploy_projects ${PROJECT_NAME}
    gcloud billing projects link ${PROJECT_NAME} --billing-account ${BILLING_ACCOUNT}
    gcloud --project ${PROJECT_NAME} services enable secretmanager.googleapis.com
    gcloud --project ${PROJECT_NAME} secrets describe ${SECRET_NAME} || gcloud --project ${PROJECT_NAME} secrets create ${SECRET_NAME}
    echo -n ${secret} | gcloud --project ${PROJECT_NAME} secrets versions add ${SECRET_NAME} --data-file=/dev/fd/0 
    gcloud app create --project ${PROJECT_NAME} --region ${REGION} || echo "App Engine already created for ${PROJECT_NAME}"
    gcloud projects add-iam-policy-binding ${PROJECT_NAME} --member=${service_account_name} --role=roles/storage.admin
    gcloud projects add-iam-policy-binding ${PROJECT_NAME} --member=${service_account_name} --role=roles/artifactregistry.createOnPushWriter
    gcloud --project ${PROJECT_NAME} secrets add-iam-policy-binding ${SECRET_NAME} --member=${service_account_name} --role=roles/secretmanager.secretAccessor
    sleep 120 # Wait for IAM policies to propagate
    gcloud --quiet --project ${PROJECT_NAME} app deploy appengine_mailer
done