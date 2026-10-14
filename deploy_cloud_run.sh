#!/usr/bin/env bash
# Deploy Project A.E.G.I.S. to Google Cloud Run
set -e

PROJECT_ID=$(gcloud config get-value project)
SERVICE_NAME="aegis-copilot"
REGION="asia-northeast1"

echo "=========================================================="
echo "🚀 Deploying Project A.E.G.I.S. to Google Cloud Run"
echo "Project ID: $PROJECT_ID"
echo "Service:    $SERVICE_NAME"
echo "Region:     $REGION"
echo "=========================================================="

# Build and deploy using Google Cloud Run source-based deploy or Cloud Build
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$REGION" \
  --platform managed \
  --allow-unauthenticated \
  --port 8080 \
  --set-env-vars GEMINI_API_KEY="${GEMINI_API_KEY:-}"

SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --platform managed --region "$REGION" --format 'value(status.url)')

echo "=========================================================="
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "Public Cloud Run URL: $SERVICE_URL"
echo "Use this URL in your Zenn Hackathon submission!"
echo "=========================================================="
