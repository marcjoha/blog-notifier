#!/bin/bash

# --- Configuration ---
JOB_NAME="blog-notifier"
JOB_REGION="europe-north2"
SCHEDULE_NAME="blog-notifier-schedule"
SCHEDULE_DESCRIPTION="Runs the blog-notifier job every weekday at 9:30 Swedish time"
TIMEZONE="Europe/Stockholm"
CRON_EXPRESSION="30 9 * * 1-5" # 9:30 AM every weekday (Monday-Friday)

# --- Input Validation ---

# Prompt for the webhook URL
read -p "Enter the BLOG_NOTIFIER_WEBHOOK: " BLOG_NOTIFIER_WEBHOOK
# Validate that the user provided a value
while [[ -z "$BLOG_NOTIFIER_WEBHOOK" ]]; do
  echo "BLOG_NOTIFIER_WEBHOOK cannot be empty."
  read -p "Enter the BLOG_NOTIFIER_WEBHOOK: " BLOG_NOTIFIER_WEBHOOK
done

# Prompt for the GCP project ID
read -p "Enter the BLOG_NOTIFIER_GCP_PROJECT: " BLOG_NOTIFIER_GCP_PROJECT
# Validate that the user provided a value
while [[ -z "$BLOG_NOTIFIER_GCP_PROJECT" ]]; do
  echo "BLOG_NOTIFIER_GCP_PROJECT cannot be empty."
  read -p "Enter the BLOG_NOTIFIER_GCP_PROJECT: " BLOG_NOTIFIER_GCP_PROJECT
done

# --- Deployment ---

echo "Deploying Cloud Run Job..."
gcloud run jobs deploy "$JOB_NAME" \
  --source . \
  --region "$JOB_REGION" \
  --set-env-vars "BLOG_NOTIFIER_WEBHOOK=$BLOG_NOTIFIER_WEBHOOK,BLOG_NOTIFIER_GCP_PROJECT=$BLOG_NOTIFIER_GCP_PROJECT"

if [[ $? -ne 0 ]]; then
  echo "Error deploying Cloud Run Job. Exiting."
  exit 1
fi

echo "Deployment initiated with the following environment variables:"
echo "BLOG_NOTIFIER_WEBHOOK: $BLOG_NOTIFIER_WEBHOOK"
echo "BLOG_NOTIFIER_GCP_PROJECT: $BLOG_NOTIFIER_GCP_PROJECT"

# --- Cloud Scheduler ---

echo "Creating or updating Cloud Scheduler job..."
gcloud scheduler jobs describe "$SCHEDULE_NAME" --location="$JOB_REGION" > /dev/null 2>&1
if [[ $? -eq 0 ]]; then
  echo "Scheduler job '$SCHEDULE_NAME' already exists. Updating..."
  gcloud scheduler jobs update http "$SCHEDULE_NAME" \
    --location="$JOB_REGION" \
    --schedule="$CRON_EXPRESSION" \
    --time-zone="$TIMEZONE" \
    --description="$SCHEDULE_DESCRIPTION" \
    --uri="https://$JOB_REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$(gcloud config get-value project)/jobs/$JOB_NAME:run" \
    --http-method="POST" \
    --oidc-service-account-email="$(gcloud config get-value account)"
else
  echo "Scheduler job '$SCHEDULE_NAME' does not exist. Creating..."
  gcloud scheduler jobs create http "$SCHEDULE_NAME" \
    --location="$JOB_REGION" \
    --schedule="$CRON_EXPRESSION" \
    --time-zone="$TIMEZONE" \
    --description="$SCHEDULE_DESCRIPTION" \
    --uri="https://$JOB_REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/$(gcloud config get-value project)/jobs/$JOB_NAME:run" \
    --http-method="POST" \
    --oidc-service-account-email="$(gcloud config get-value account)"
fi

if [[ $? -ne 0 ]]; then
  echo "Error creating/updating Cloud Scheduler job. Exiting."
  exit 1
fi

echo "Cloud Scheduler job '$SCHEDULE_NAME' configured to run '$JOB_NAME' every weekday at 9:30 Swedish time."
