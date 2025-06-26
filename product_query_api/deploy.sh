#!/bin/bash

# Exit on any error
set -e

echo "Building Docker image..."
docker build --platform linux/amd64 -t gcr.io/buoyant-yew-463209-k5/product-query-api:latest .

echo "Pushing Docker image..."
docker push gcr.io/buoyant-yew-463209-k5/product-query-api:latest

echo "Deploying to Cloud Run..."
gcloud run deploy product-query-api \
  --image gcr.io/buoyant-yew-463209-k5/product-query-api:latest \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 80 \
  --max-instances 10

echo "Setting IAM permissions..."
gcloud run services add-iam-policy-binding product-query-api \
  --region=us-central1 \
  --member="serviceAccount:service-299758382103@gcf-admin-robot.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud run services add-iam-policy-binding product-query-api \
  --region=us-central1 \
  --member="serviceAccount:service-299758382103@gcf-admin-robot.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

echo "Deployment complete!"
echo "Service URL: https://product-query-api-nxbmt7mfiq-uc.a.run.app"
echo ""
echo "Available endpoints:"
echo "  POST /query - Query a product summary"
echo "  GET  /search?q=<query> - Search products"
echo "  GET  /stats - Get statistics"
echo "  GET  /health - Health check" 