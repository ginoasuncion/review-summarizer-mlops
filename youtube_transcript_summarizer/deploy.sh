#!/bin/bash

set -e

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
REGION="us-central1"
SERVICE_NAME="youtube-transcript-summarizer"
REPOSITORY="youtube-transcript-summarizer"
IMAGE_NAME="youtube-transcript-summarizer"
SOURCE_BUCKET="youtube-processed-data-bucket"
SUMMARIES_BUCKET="youtube-processed-data-bucket"

echo "🚀 Deploying YouTube Transcript Summarizer Cloud Function..."

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
    --set-env-vars="SOURCE_BUCKET=$SOURCE_BUCKET,SUMMARIES_BUCKET=$SUMMARIES_BUCKET" \
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
TOPIC_NAME="youtube-transcript-summarizer-trigger"
gcloud pubsub topics create $TOPIC_NAME --project=$PROJECT_ID || echo "Topic already exists"

# Create subscription
SUBSCRIPTION_NAME="youtube-transcript-summarizer-subscription"
gcloud pubsub subscriptions create $SUBSCRIPTION_NAME \
    --topic $TOPIC_NAME \
    --push-endpoint $SERVICE_URL/process \
    --project=$PROJECT_ID || echo "Subscription already exists"

# Create Cloud Storage notification
gsutil notification create -t $TOPIC_NAME -f json gs://$SOURCE_BUCKET || echo "Notification already exists"

echo "🎉 YouTube Transcript Summarizer deployment complete!"

echo ""
echo "📋 Summary:"
echo "   Service: $SERVICE_NAME"
echo "   URL: $SERVICE_URL"
echo "   Source Bucket: gs://$SOURCE_BUCKET"
echo "   Summaries Bucket: gs://$SUMMARIES_BUCKET"
echo "   Trigger: Cloud Storage OBJECT_FINALIZE events on transcripts/"

echo ""
echo "🔧 Next steps:"
echo "   1. Set OPENAI_API_KEY environment variable"
echo "   2. Test by uploading a transcript file to gs://$SOURCE_BUCKET/transcripts/"
echo "   3. Check summaries in gs://$SUMMARIES_BUCKET/summaries/"
echo "   4. Monitor logs: gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME' --project=$PROJECT_ID" 