#!/bin/bash

# YouTube API GCP Setup Script

set -e

# Configuration
PROJECT_ID=${1:-"your-project-id"}  # Pass project ID as first argument
REGION="us-central1"
SERVICE_NAME="youtube-search-api"
BUCKET_NAME="youtube-data-pipeline"
SERVICE_ACCOUNT_NAME="youtube-api-sa"

echo "🔧 Setting up GCP infrastructure for YouTube API..."
echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Service: $SERVICE_NAME"
echo "   Bucket: $BUCKET_NAME"
echo "   Service Account: $SERVICE_ACCOUNT_NAME"

# Check if project ID is provided
if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo "❌ Error: Please provide your GCP project ID as the first argument"
    echo "Usage: ./setup.sh YOUR_PROJECT_ID"
    exit 1
fi

# Set the project
echo "🔧 Setting GCP project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔌 Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable storage.googleapis.com
gcloud services enable iam.googleapis.com

# Create GCS bucket
echo "🪣 Creating GCS bucket..."
gsutil mb -l $REGION gs://$BUCKET_NAME 2>/dev/null || echo "Bucket already exists"

# Create service account
echo "👤 Creating service account..."
gcloud iam service-accounts create $SERVICE_ACCOUNT_NAME \
    --display-name="YouTube API Service Account" \
    --description="Service account for YouTube Search API" \
    2>/dev/null || echo "Service account already exists"

# Grant necessary permissions
echo "🔐 Granting permissions..."

# Storage permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"

# Cloud Run permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/run.invoker"

# Create service account key (optional - for local development)
echo "🔑 Creating service account key for local development..."
gcloud iam service-accounts keys create youtube-api-key.json \
    --iam-account=$SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com \
    2>/dev/null || echo "Key file already exists"

echo "✅ GCP infrastructure setup completed!"
echo ""
echo "📝 Next steps:"
echo "1. Set environment variables in Cloud Run:"
echo "   - OXYLABS_USERNAME"
echo "   - OXYLABS_PASSWORD"
echo ""
echo "2. Deploy the API:"
echo "   ./deploy.sh $PROJECT_ID"
echo ""
echo "3. For local development, use the service account key:"
echo "   export GOOGLE_APPLICATION_CREDENTIALS=./youtube-api-key.json"

# Grant eventarc.eventReceiver role
echo "🔐 Granting eventarc.eventReceiver role..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:youtube-api-sa@$PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/eventarc.eventReceiver"

echo "✅ Eventarc.eventReceiver role granted!" 