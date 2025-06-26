#!/bin/bash

# YouTube Data Processor Cloud Function Deployment Script

set -e

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
REGION="us-central1"
SERVICE_NAME="youtube-data-processor"
SOURCE_BUCKET="youtube-search-data-bucket"
DESTINATION_BUCKET="youtube-processed-data-bucket"
REPOSITORY="youtube-data-processor"

echo "🚀 Deploying YouTube Data Processor Cloud Function..."

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable artifactregistry.googleapis.com --project=$PROJECT_ID
gcloud services enable run.googleapis.com --project=$PROJECT_ID
gcloud services enable pubsub.googleapis.com --project=$PROJECT_ID

# Create Artifact Registry repository if it doesn't exist
echo "📦 Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPOSITORY \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID 2>/dev/null || echo "Repository already exists"

# Build and push the Docker image
echo "📦 Building Docker image..."
IMAGE_NAME="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE_NAME"
docker build --platform linux/amd64 -t $IMAGE_NAME .

echo "📤 Pushing Docker image..."
docker push $IMAGE_NAME

# Create the destination bucket if it doesn't exist
echo "🪣 Creating destination bucket..."
gsutil mb -p $PROJECT_ID -c STANDARD -l $REGION gs://$DESTINATION_BUCKET 2>/dev/null || echo "Bucket already exists"

# Deploy to Cloud Run
echo "☁️ Deploying to Cloud Run..."
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
    --set-env-vars "SOURCE_BUCKET=$SOURCE_BUCKET,DESTINATION_BUCKET=$DESTINATION_BUCKET,GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --service-account="youtube-api-sa@$PROJECT_ID.iam.gserviceaccount.com"

# Get the service URL
SERVICE_URL="https://youtube-data-processor-nxbmt7mfiq-uc.a.run.app"

echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"

# Set up Cloud Storage trigger
echo "🔗 Setting up Cloud Storage trigger..."

# Create a Pub/Sub topic for the trigger
TOPIC_NAME="youtube-data-processor-trigger"
gcloud pubsub topics create $TOPIC_NAME --project $PROJECT_ID 2>/dev/null || echo "Topic already exists"

# Create a Pub/Sub subscription
SUBSCRIPTION_NAME="youtube-data-processor-subscription"
gcloud pubsub subscriptions create $SUBSCRIPTION_NAME \
    --topic $TOPIC_NAME \
    --push-endpoint $SERVICE_URL/process \
    --push-auth-service-account="youtube-api-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --project $PROJECT_ID 2>/dev/null || echo "Subscription already exists"

# Set up Cloud Storage notification
NOTIFICATION_NAME="youtube-data-processor-notification"
gsutil notification create -t $TOPIC_NAME -f json gs://$SOURCE_BUCKET 2>/dev/null || echo "Notification already exists"

echo "🎉 YouTube Data Processor deployment complete!"
echo ""
echo "📋 Summary:"
echo "   Service: $SERVICE_NAME"
echo "   URL: $SERVICE_URL"
echo "   Source Bucket: gs://$SOURCE_BUCKET"
echo "   Destination Bucket: gs://$DESTINATION_BUCKET"
echo "   Trigger: Cloud Storage OBJECT_FINALIZE events"
echo ""
echo "🔧 Next steps:"
echo "   1. Test by uploading a JSON file to gs://$SOURCE_BUCKET"
echo "   2. Check the processed data in gs://$DESTINATION_BUCKET"
echo "   3. Monitor logs: gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --project=$PROJECT_ID" 