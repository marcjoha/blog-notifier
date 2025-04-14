#!/bin/bash

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

# Deploy the Cloud Run Job with the provided environment variables
gcloud run jobs deploy blog-notifier \
  --source . \
  --set-env-vars "BLOG_NOTIFIER_WEBHOOK=$BLOG_NOTIFIER_WEBHOOK,BLOG_NOTIFIER_GCP_PROJECT=$BLOG_NOTIFIER_GCP_PROJECT"

echo "Deployment initiated with the following environment variables:"
echo "BLOG_NOTIFIER_WEBHOOK: $BLOG_NOTIFIER_WEBHOOK"
echo "BLOG_NOTIFIER_GCP_PROJECT: $BLOG_NOTIFIER_GCP_PROJECT"
