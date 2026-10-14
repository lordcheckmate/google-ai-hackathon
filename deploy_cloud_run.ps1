# Deploy AI Meeting Assistant to Google Cloud Run
$ErrorActionPreference = "Stop"

$gcloudCmd = "C:\Users\saega\google-cloud-sdk\google-cloud-sdk\bin\gcloud.cmd"
if (-not (Test-Path $gcloudCmd)) {
    $gcloudCmd = "gcloud"
}

$projectId = (& $gcloudCmd config get-value project 2>$null)
if (-not $projectId) {
    Write-Host "Please set your Google Cloud Project first: gcloud config set project YOUR_PROJECT_ID" -ForegroundColor Red
    exit 1
}

$serviceName = "ai-meeting-assistant"
$region = "us-central1"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🚀 Deploying AI Meeting Assistant to Google Cloud Run" -ForegroundColor Cyan
Write-Host "Project ID: $projectId" -ForegroundColor Yellow
Write-Host "Service:    $serviceName" -ForegroundColor Yellow
Write-Host "Region:     $region" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

& $gcloudCmd run deploy $serviceName `
  --source . `
  --region $region `
  --platform managed `
  --allow-unauthenticated `
  --timeout 3600 `
  --session-affinity `
  --min-instances 0 `
  --max-instances 3 `
  --cpu-boost `
  --memory 1Gi `
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_LOCATION=us-central1,REASONING_MODEL=gemini-2.5-flash,IMAGE_MODEL=gemini-3.1-flash-image

$serviceUrl = (& $gcloudCmd run services describe $serviceName --platform managed --region $region --format "value(status.url)")

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "🎉 DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "Public Cloud Run URL: $serviceUrl" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
