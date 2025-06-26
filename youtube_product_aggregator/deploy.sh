#!/bin/bash

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
REGION="us-central1"
SERVICE_NAME="youtube-product-aggregator"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

# Processing Configuration
MIN_REVIEWS_PER_PRODUCT=${MIN_REVIEWS_PER_PRODUCT:-2}
WAIT_TIME_MINUTES=${WAIT_TIME_MINUTES:-3}
QUERY_BASED_PROCESSING=${QUERY_BASED_PROCESSING:-true}

# Build and push Docker image
echo "Building Docker image..."
docker build --platform linux/amd64 -t $IMAGE_NAME .

echo "Pushing Docker image..."
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --max-instances 10 \
  --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID" \
  --set-env-vars="SOURCE_BUCKET=youtube-processed-data-bucket" \
  --set-env-vars="PRODUCTS_BUCKET=youtube-processed-data-bucket" \
  --set-env-vars="MIN_REVIEWS_PER_PRODUCT=$MIN_REVIEWS_PER_PRODUCT" \
  --set-env-vars="WAIT_TIME_MINUTES=$WAIT_TIME_MINUTES" \
  --set-env-vars="QUERY_BASED_PROCESSING=$QUERY_BASED_PROCESSING"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format="value(status.url)")

echo "Service deployed successfully!"
echo "Service URL: $SERVICE_URL"
echo "Configuration:"
echo "  - Min reviews per product: $MIN_REVIEWS_PER_PRODUCT"
echo "  - Wait time: $WAIT_TIME_MINUTES minutes"
echo "  - Query-based processing: $QUERY_BASED_PROCESSING"

# Set up Cloud Storage notification for all relevant files
echo "Setting up Cloud Storage notification..."
gsutil notification create -t youtube-product-aggregator-topic -f json gs://youtube-processed-data-bucket

# Create Pub/Sub subscription
echo "Creating Pub/Sub subscription..."
gcloud pubsub subscriptions create youtube-product-aggregator-sub \
  --topic youtube-product-aggregator-topic \
  --push-endpoint="$SERVICE_URL/process" \
  --ack-deadline=60

echo "Deployment complete!" 