#!/bin/bash

# --- Configuration ---
DEFAULT_GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
DEFAULT_JOB_REGION="europe-north2"
DEFAULT_AI_REGION="europe-north1"

# --- Input Validation ---

# Prompt for the webhook URL
read -p "Enter the CHAT_WEBHOOK: " CHAT_WEBHOOK
# Validate that the user provided a value
while [[ -z "$CHAT_WEBHOOK" ]]; do
  echo "CHAT_WEBHOOK cannot be empty."
  read -p "Enter the CHAT_WEBHOOK: " CHAT_WEBHOOK
done

# Prompt for the GCP project ID
read -p "Enter the GOOGLE_CLOUD_PROJECT (default: $DEFAULT_GOOGLE_CLOUD_PROJECT): " GOOGLE_CLOUD_PROJECT
# If the user presses enter without typing anything, use the default project
if [[ -z "$GOOGLE_CLOUD_PROJECT" ]]; then
  GOOGLE_CLOUD_PROJECT="$DEFAULT_GOOGLE_CLOUD_PROJECT"
fi

# Prompt for the Cloud Run job region
read -p "Enter the JOB_REGION (default: $DEFAULT_JOB_REGION): " JOB_REGION
# If the user presses enter without typing anything, use the default project
if [[ -z "$JOB_REGION" ]]; then
  JOB_REGION="$DEFAULT_JOB_REGION"
fi

# Prompt for the Cloud Run job region
read -p "Enter the AI_REGION (default: $DEFAULT_AI_REGION): " AI_REGION
# If the user presses enter without typing anything, use the default project
if [[ -z "$AI_REGION" ]]; then
  AI_REGION="$DEFAULT_AI_REGION"
fi

# --- Deployment ---

echo "Deploying Cloud Run job..."
gcloud run jobs deploy blog-notifier \
  --source . \
  --region "$JOB_REGION" \
  --set-env-vars "CHAT_WEBHOOK=$CHAT_WEBHOOK,GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,AI_REGION=$AI_REGION"

if [[ $? -ne 0 ]]; then
  echo "Error deploying Cloud Run job. Exiting."
  exit 1
fi
