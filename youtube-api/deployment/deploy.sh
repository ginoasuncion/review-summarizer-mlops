#!/bin/bash

# YouTube Search API Cloud Run Deployment Script

set -e

# Configuration
PROJECT_ID=${1:-"your-project-id"}  # Pass project ID as first argument
REGION="us-central1"
SERVICE_NAME="youtube-search-api"
BUCKET_NAME="youtube-data-pipeline"
SERVICE_ACCOUNT_NAME="youtube-api-sa"

echo "🚀 Deploying YouTube Search API to Cloud Run..."
echo "📋 Configuration:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Service: $SERVICE_NAME"
echo "   Bucket: $BUCKET_NAME"

# Check if project ID is provided
if [ "$PROJECT_ID" = "your-project-id" ]; then
    echo "❌ Error: Please provide your GCP project ID as the first argument"
    echo "Usage: ./deploy.sh YOUR_PROJECT_ID"
    exit 1
fi

# Set the project
echo "🔧 Setting GCP project..."
gcloud config set project $PROJECT_ID

# Check if service account exists
echo "🔍 Checking service account..."
if ! gcloud iam service-accounts describe $SERVICE_ACCOUNT_NAME@$PROJECT_ID.iam.gserviceaccount.com >/dev/null 2>&1; then
    echo "❌ Service account not found. Please run setup.sh first:"
    echo "   ./setup.sh $PROJECT_ID"
    exit 1
fi

# Build and deploy using Cloud Build
echo "🏗️ Building and deploying with Cloud Build..."
gcloud builds submit --config deployment/cloudbuild.yaml .

# Set environment variables for Oxylabs credentials
echo "🔐 Setting environment variables..."
echo "Please enter your Oxylabs credentials:"
read -p "OXYLABS_USERNAME: " OXYLABS_USERNAME
read -s -p "OXYLABS_PASSWORD: " OXYLABS_PASSWORD
echo

# Update Cloud Run service with environment variables
echo "⚙️ Updating service with environment variables..."
gcloud run services update $SERVICE_NAME \
    --region=$REGION \
    --set-env-vars="OXYLABS_USERNAME=$OXYLABS_USERNAME,OXYLABS_PASSWORD=$OXYLABS_PASSWORD"

# Get the service URL
echo "🔗 Getting service URL..."
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")

echo "✅ Deployment completed successfully!"
echo "🌐 Service URL: $SERVICE_URL"
echo ""
echo "📝 Usage examples:"
echo "   Health check: curl $SERVICE_URL/health"
echo "   Search: curl -X POST $SERVICE_URL/search \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"query\": \"tesla model 3 review\"}'"
echo ""
echo "🔐 Environment variables set:"
echo "   - OXYLABS_USERNAME: [configured]"
echo "   - OXYLABS_PASSWORD: [configured]"
echo "   - GCP_PROJECT_ID: $PROJECT_ID"
echo "   - GCP_BUCKET_NAME: $BUCKET_NAME" 