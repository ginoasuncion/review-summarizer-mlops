#!/bin/bash

# Cloud Functions Deployment Script for YouTube Data Pipeline

set -e

# Configuration
PROJECT_ID=${1:-"your-project-id"}  # Pass project ID as first argument
REGION="us-central1"
BUCKET_NAME="youtube-data-pipeline"
PARSED_BUCKET_NAME="${BUCKET_NAME}-parsed"
TRANSCRIPTS_BUCKET_NAME="${BUCKET_NAME}-transcripts"

echo "🚀 Deploying Cloud Functions for YouTube Data Pipeline..."
echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Raw Bucket: $BUCKET_NAME"
echo "   Parsed Bucket: $PARSED_BUCKET_NAME"
echo "   Transcripts Bucket: $TRANSCRIPTS_BUCKET_NAME"

# Check if project ID is provided
if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo "❌ Error: Please provide your GCP project ID as the first argument"
    echo "Usage: ./deploy_functions.sh YOUR_PROJECT_ID"
    exit 1
fi

# Set the project
echo "🔧 Setting GCP project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable bigquery.googleapis.com

# Create buckets if they don't exist
echo "🪣 Creating buckets..."
gsutil mb -l $REGION gs://$PARSED_BUCKET_NAME 2>/dev/null || echo "Bucket $PARSED_BUCKET_NAME already exists"
gsutil mb -l $REGION gs://$TRANSCRIPTS_BUCKET_NAME 2>/dev/null || echo "Bucket $TRANSCRIPTS_BUCKET_NAME already exists"

# Deploy Parse Videos Function
echo "🏗️ Deploying Parse Videos Function..."
gcloud functions deploy parse-videos \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source=functions/parse_videos \
    --entry-point=parse_videos_trigger \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=$BUCKET_NAME" \
    --trigger-location=$REGION \
    --memory=512MB \
    --timeout=540s \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_BUCKET_NAME=$BUCKET_NAME" \
    --service-account="youtube-api-sa@$PROJECT_ID.iam.gserviceaccount.com"

# Deploy Get Transcripts Function
echo "🏗️ Deploying Get Transcripts Function..."
gcloud functions deploy get-transcripts \
    --gen2 \
    --runtime=python311 \
    --region=$REGION \
    --source=functions/get_transcripts \
    --entry-point=get_transcripts_trigger \
    --trigger-event-filters="type=google.cloud.storage.object.v1.finalized" \
    --trigger-event-filters="bucket=$PARSED_BUCKET_NAME" \
    --trigger-location=$REGION \
    --memory=512MB \
    --timeout=540s \
    --set-env-vars="GCP_PROJECT_ID=$PROJECT_ID,GCP_BUCKET_NAME=$BUCKET_NAME" \
    --service-account="youtube-api-sa@$PROJECT_ID.iam.gserviceaccount.com"

# Grant additional permissions to service account
echo "🔐 Granting BigQuery permissions..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:youtube-api-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:youtube-api-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/bigquery.jobUser"

echo "✅ Cloud Functions deployment completed!"
echo ""
echo "📝 Pipeline Flow:"
echo "1. Raw data uploaded to gs://$BUCKET_NAME/raw/ → triggers parse-videos function"
echo "2. Parsed data saved to gs://$PARSED_BUCKET_NAME/videos/ → triggers get-transcripts function"
echo "3. Transcripts saved to gs://$TRANSCRIPTS_BUCKET_NAME/transcripts/"
echo ""
echo "📊 BigQuery Tables:"
echo "   - youtube_data.staging_videos (video information)"
echo "   - youtube_data.video_transcripts (transcript data)"
echo ""
echo "🧪 Test the pipeline:"
echo "   curl -X POST https://your-service-url/search \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"query\": \"iPhone 15 review\", \"max_results\": 3}'" 