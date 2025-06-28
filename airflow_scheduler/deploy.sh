#!/bin/bash

# Deploy Airflow Scheduler Service to Google Cloud Run

set -e

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
SERVICE_NAME="airflow-scheduler"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying Airflow Scheduler Service..."

# Build and push Docker image
echo "📦 Building Docker image..."
docker build --platform linux/amd64 -t $IMAGE_NAME .

echo "📤 Pushing image to Google Container Registry..."
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 2Gi \
    --cpu 2 \
    --timeout 3600 \
    --concurrency 80 \
    --max-instances 10 \
    --set-env-vars="AIRFLOW_BASE_URL=http://localhost:8080,AIRFLOW_USERNAME=airflow,AIRFLOW_PASSWORD=airflow" \
    --port 8000

echo "✅ Airflow Scheduler Service deployed successfully!"
echo "🌍 Service URL: $(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')" 