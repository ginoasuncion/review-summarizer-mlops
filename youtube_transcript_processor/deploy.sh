#!/bin/bash

set -e

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
REGION="us-central1"
SERVICE_NAME="youtube-transcript-processor"
REPOSITORY="youtube-transcript-processor"
IMAGE_NAME="youtube-transcript-processor"
SOURCE_BUCKET="youtube-processed-data-bucket"
TRANSCRIPTS_BUCKET="youtube-processed-data-bucket"

echo "🚀 Deploying YouTube Transcript Processor Cloud Function..."

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID
gcloud services enable run.googleapis.com --project=$PROJECT_ID
gcloud services enable storage.googleapis.com --project=$PROJECT_ID

# Create Artifact Registry repository
echo "📦 Creating Artifact Registry repository..."
gcloud artifacts repositories create $REPOSITORY \
    --repository-format=docker \
    --location=$REGION \
    --project=$PROJECT_ID || echo "Repository already exists"

# Build Docker image
echo "📦 Building Docker image..."
docker build --platform linux/amd64 -t $IMAGE_NAME .

# Tag and push to Artifact Registry
echo "📤 Pushing Docker image..."
docker tag $IMAGE_NAME $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest

# Deploy to Cloud Run
echo "☁️ Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest \
    --platform managed \
    --region $REGION \
    --project $PROJECT_ID \
    --allow-unauthenticated \
    --set-env-vars="SOURCE_BUCKET=$SOURCE_BUCKET,TRANSCRIPTS_BUCKET=$TRANSCRIPTS_BUCKET" \
    --memory 1Gi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --project=$PROJECT_ID --format="value(status.url)")

echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"

# Set up Cloud Storage trigger
echo "🔗 Setting up Cloud Storage trigger..."

# Create Pub/Sub topic
TOPIC_NAME="youtube-transcript-processor-trigger"
gcloud pubsub topics create $TOPIC_NAME --project=$PROJECT_ID || echo "Topic already exists"

# Create subscription
SUBSCRIPTION_NAME="youtube-transcript-processor-subscription"
gcloud pubsub subscriptions create $SUBSCRIPTION_NAME \
    --topic $TOPIC_NAME \
    --push-endpoint $SERVICE_URL/process \
    --project=$PROJECT_ID || echo "Subscription already exists"

# Create Cloud Storage notification
gsutil notification create -t $TOPIC_NAME -f json gs://$SOURCE_BUCKET || echo "Notification already exists"

echo "🎉 YouTube Transcript Processor deployment complete!"

echo ""
echo "📋 Summary:"
echo "   Service: $SERVICE_NAME"
echo "   URL: $SERVICE_URL"
echo "   Source Bucket: gs://$SOURCE_BUCKET"
echo "   Transcripts Bucket: gs://$TRANSCRIPTS_BUCKET"
echo "   Trigger: Cloud Storage OBJECT_FINALIZE events on processed/videos/"

echo ""
echo "🔧 Next steps:"
echo "   1. Set OXYLABS_USERNAME and OXYLABS_PASSWORD environment variables"
echo "   2. Test by uploading a video file to gs://$SOURCE_BUCKET/processed/videos/"
echo "   3. Check transcripts in gs://$TRANSCRIPTS_BUCKET/transcripts/"
echo "   4. Monitor logs: gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --project=$PROJECT_ID" 