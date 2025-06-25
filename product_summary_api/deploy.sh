#!/bin/bash

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
SERVICE_NAME="product-summary-api"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "Building and deploying Product Summary API..."

# Build the Docker image
echo "Building Docker image..."
docker build -t $IMAGE_NAME .

# Push to Google Container Registry
echo "Pushing to Google Container Registry..."
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 80 \
  --max-instances 10 \
  --set-env-vars "GCP_PROJECT_ID=$PROJECT_ID,BIGQUERY_DATASET=youtube_reviews,BIGQUERY_PROJECT=$PROJECT_ID"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --project $PROJECT_ID --format="value(status.url)")

echo "Deployment complete!"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Test the service:"
echo "curl -X GET $SERVICE_URL/health"
echo ""
echo "Generate a product summary:"
echo "curl -X POST $SERVICE_URL/generate-summary \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"search_query\": \"Adidas Ultraboost review\"}'" 