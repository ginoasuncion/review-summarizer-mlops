#!/bin/bash

# Deploy LLM Judge API to Cloud Run
gcloud run deploy llm-judge-api \
  --source . \
  --region=us-central1 \
  --allow-unauthenticated \
  --project=buoyant-yew-463209-k5

echo "LLM Judge API deployed successfully!"
echo "Don't forget to set the OPENAI_API_KEY environment variable:"
echo "gcloud run services update llm-judge-api --set-env-vars OPENAI_API_KEY=your-api-key --region=us-central1 --project=buoyant-yew-463209-k5" 