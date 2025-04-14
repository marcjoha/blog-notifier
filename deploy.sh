#!/bin/bash

# --- Configuration ---
JOB_NAME="blog-notifier"
JOB_REGION="europe-north2"

# --- Input Validation ---

# Prompt for the webhook URL
read -p "Enter the BLOG_NOTIFIER_WEBHOOK: " BLOG_NOTIFIER_WEBHOOK
# Validate that the user provided a value
while [[ -z "$BLOG_NOTIFIER_WEBHOOK" ]]; do
  echo "BLOG_NOTIFIER_WEBHOOK cannot be empty."
  read -p "Enter the BLOG_NOTIFIER_WEBHOOK: " BLOG_NOTIFIER_WEBHOOK
done

# Get the default project from gcloud config
DEFAULT_PROJECT=$(gcloud config get-value project)

# Prompt for the GCP project ID with a default value
read -p "Enter the BLOG_NOTIFIER_GCP_PROJECT (default: $DEFAULT_PROJECT): " BLOG_NOTIFIER_GCP_PROJECT
# If the user presses enter without typing anything, use the default project
if [[ -z "$BLOG_NOTIFIER_GCP_PROJECT" ]]; then
  BLOG_NOTIFIER_GCP_PROJECT="$DEFAULT_PROJECT"
fi

# Validate that the user provided a value (or the default was used)
while [[ -z "$BLOG_NOTIFIER_GCP_PROJECT" ]]; do
  echo "BLOG_NOTIFIER_GCP_PROJECT cannot be empty."
  read -p "Enter the BLOG_NOTIFIER_GCP_PROJECT (default: $DEFAULT_PROJECT): " BLOG_NOTIFIER_GCP_PROJECT
  if [[ -z "$BLOG_NOTIFIER_GCP_PROJECT" ]]; then
    BLOG_NOTIFIER_GCP_PROJECT="$DEFAULT_PROJECT"
  fi
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
