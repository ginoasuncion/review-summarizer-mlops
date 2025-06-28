#!/bin/bash

# Deploy Frontend to Google Cloud Run

set -e

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
SERVICE_NAME="shoe-review-ui"
REGION="us-central1"
IMAGE_NAME="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo "🚀 Deploying Shoe Review UI..."

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Build the React app
echo "🔨 Building React app..."
npm run build

# Create Dockerfile for production build
echo "🐳 Creating Dockerfile..."
cat > Dockerfile << 'EOF'
FROM nginx:alpine

# Copy built React app
COPY build /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Expose port
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
EOF

# Create nginx configuration
echo "⚙️ Creating nginx configuration..."
cat > nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    server {
        listen 8080;
        server_name localhost;
        root /usr/share/nginx/html;
        index index.html;

        # Handle React Router
        location / {
            try_files $uri $uri/ /index.html;
        }

        # Cache static assets
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }
}
EOF

# Build and push Docker image
echo "📦 Building Docker image..."
docker build --platform linux/amd64 -t $IMAGE_NAME .

echo "📤 Pushing image to Google Container Registry..."
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --concurrency 80 \
    --max-instances 10 \
    --port 8080

echo "✅ Shoe Review UI deployed successfully!"
echo "🌍 Service URL: $(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')"

# Cleanup
echo "🧹 Cleaning up..."
rm -f Dockerfile nginx.conf

echo "🎉 Deployment complete!" 