# Deploy Project A.E.G.I.S. to Google Cloud Run (PowerShell)
$ErrorActionPreference = "Stop"

$projectId = (gcloud config get-value project 2>$null)
if (-not $projectId) {
    Write-Host "Please log into Google Cloud first: gcloud auth login && gcloud config set project YOUR_PROJECT_ID" -ForegroundColor Red
    exit 1
}

$serviceName = "aegis-copilot"
$region = "asia-northeast1"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🚀 Deploying Project A.E.G.I.S. to Google Cloud Run" -ForegroundColor Cyan
Write-Host "Project ID: $projectId" -ForegroundColor Yellow
Write-Host "Service:    $serviceName" -ForegroundColor Yellow
Write-Host "Region:     $region" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

gcloud run deploy $serviceName `
  --source . `
  --region $region `
  --platform managed `
  --allow-unauthenticated `
  --port 8080 `
  --set-env-vars GEMINI_API_KEY="$($env:GEMINI_API_KEY)"

$serviceUrl = (gcloud run services describe $serviceName --platform managed --region $region --format 'value(status.url)')

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "🎉 DEPLOYMENT SUCCESSFUL!" -ForegroundColor Green
Write-Host "Public Cloud Run URL: $serviceUrl" -ForegroundColor Cyan
Write-Host "Use this URL in your Zenn Hackathon submission!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
