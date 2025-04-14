#!/bin/bash

# --- Configuration ---
JOB_NAME="blog-notifier"
JOB_REGION="europe-north2"

# --- Input Validation ---

# Prompt for the webhook URL
read -p "Enter the CHAT_WEBHOOK: " CHAT_WEBHOOK
# Validate that the user provided a value
while [[ -z "$CHAT_WEBHOOK" ]]; do
  echo "CHAT_WEBHOOK cannot be empty."
  read -p "Enter the CHAT_WEBHOOK: " CHAT_WEBHOOK
done

# Get the default project from gcloud config
DEFAULT_PROJECT=$(gcloud config get-value project)

# Prompt for the GCP project ID with a default value
read -p "Enter the GOOGLE_CLOUD_PROJECT (default: $DEFAULT_PROJECT): " GOOGLE_CLOUD_PROJECT
# If the user presses enter without typing anything, use the default project
if [[ -z "$GOOGLE_CLOUD_PROJECT" ]]; then
  GOOGLE_CLOUD_PROJECT="$DEFAULT_PROJECT"
fi

# Validate that the user provided a value (or the default was used)
while [[ -z "$GOOGLE_CLOUD_PROJECT" ]]; do
  echo "GOOGLE_CLOUD_PROJECT cannot be empty."
  read -p "Enter the GOOGLE_CLOUD_PROJECT (default: $DEFAULT_PROJECT): " GOOGLE_CLOUD_PROJECT
  if [[ -z "$GOOGLE_CLOUD_PROJECT" ]]; then
    GOOGLE_CLOUD_PROJECT="$DEFAULT_PROJECT"
  fi
done

# --- Deployment ---

echo "Deploying Cloud Run Job..."
gcloud run jobs deploy "$JOB_NAME" \
  --source . \
  --region "$JOB_REGION" \
  --set-env-vars "CHAT_WEBHOOK=$CHAT_WEBHOOK,GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT"

if [[ $? -ne 0 ]]; then
  echo "Error deploying Cloud Run Job. Exiting."
  exit 1
fi
