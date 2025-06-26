#!/bin/bash

# YouTube Search API Cloud Run Deployment Script

set -e

# Configuration
PROJECT_ID=${PROJECT_ID:-$(gcloud config get-value project)}
SERVICE_NAME="youtube-search-api"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying YouTube Search API to Cloud Run"
echo "Project ID: $PROJECT_ID"
echo "Service Name: $SERVICE_NAME"
echo "Region: $REGION"

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Error: Not authenticated with gcloud. Please run 'gcloud auth login'"
    exit 1
fi

# Set the project
gcloud config set project $PROJECT_ID

# Build and push the Docker image
echo "📦 Building and pushing Docker image..."
docker build --platform linux/amd64 -t $IMAGE_NAME .
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10 \
    --set-env-vars GCP_PROJECT_ID=$PROJECT_ID \
    --set-env-vars GCP_BUCKET_NAME="youtube-search-data-bucket"

echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: $(gcloud run services describe $SERVICE_NAME --region=$REGION --format='value(status.url)')"
echo ""
echo "📋 Next steps:"
echo "1. Set up your GCS bucket: 'youtube-search-data-bucket'"
echo "2. Configure environment variables for Oxylabs credentials"
echo "3. Test the API endpoints" 