# YouTube Search API

A Cloud Run service that searches YouTube videos using Oxylabs API and stores the results in Google Cloud Storage.

## Features

- 🔍 YouTube video search via Oxylabs API
- ☁️ Automatic storage to Google Cloud Storage
- 🚀 Deployed on Google Cloud Run
- 📊 Structured JSON responses
- 🏥 Health check endpoints
- 🔒 Secure credential management

## Architecture

```
Client Request → Cloud Run → Oxylabs API → YouTube Search → GCS Storage
```

## Prerequisites

- Google Cloud Platform account
- Oxylabs account with API credentials
- Docker installed locally (for local testing)
- Google Cloud SDK (gcloud) installed

## Setup

### 1. Environment Variables

Create a `.env` file in the `youtube_search_api` directory:

```bash
# GCP Configuration
GCP_PROJECT_ID=your-project-id
GCP_BUCKET_NAME=youtube-search-data-bucket

# Oxylabs Configuration
OXYLABS_USERNAME=your-oxylabs-username
OXYLABS_PASSWORD=your-oxylabs-password
```

### 2. Google Cloud Storage Bucket

Create the GCS bucket:

```bash
gsutil mb gs://youtube-search-data-bucket
```

### 3. IAM Permissions

Ensure your Cloud Run service account has the following roles:
- `Storage Object Admin` for the GCS bucket
- `Cloud Run Invoker` (if needed)

## Local Development

### Install Dependencies

```bash
cd youtube_search_api
pip install -r requirements.txt
```

### Run Locally

```bash
python main.py
```

The API will be available at `http://localhost:8080`

## Deployment

### Option 1: Using the Deployment Script

```bash
cd youtube_search_api
./deploy.sh
```

### Option 2: Using Cloud Build

```bash
gcloud builds submit --config cloudbuild.yaml .
```

### Option 3: Manual Deployment

```bash
# Build and push image
docker build -t gcr.io/PROJECT_ID/youtube-search-api .
docker push gcr.io/PROJECT_ID/youtube-search-api

# Deploy to Cloud Run
gcloud run deploy youtube-search-api \
    --image gcr.io/PROJECT_ID/youtube-search-api \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --max-instances 10
```

## API Endpoints

### Health Check

```http
GET /
```

Response:
```json
{
  "status": "healthy",
  "service": "YouTube Search API"
}
```

### Detailed Health Check

```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "gcs_connection": "ok",
  "oxylabs_configured": true
}
```

### Search YouTube

```http
POST /search
Content-Type: application/json

{
  "query": "machine learning tutorials",
  "max_results": 20
}
```

Response:
```json
{
  "status": "success",
  "message": "Search completed for 'machine learning tutorials'",
  "raw_file_path": "raw_data/youtube_search_machine_learning_tutorials_20231201_143022.json",
  "timestamp": "2023-12-01T14:30:22.123456"
}
```

## Data Storage

Search results are stored in Google Cloud Storage with the following structure:

```
gs://youtube-search-data-bucket/
└── raw_data/
    ├── youtube_search_query_1_20231201_143022.json
    ├── youtube_search_query_2_20231201_143045.json
    └── ...
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | Required |
| `GCP_BUCKET_NAME` | GCS bucket name | `youtube-search-data-bucket` |
| `OXYLABS_USERNAME` | Oxylabs API username | Required |
| `OXYLABS_PASSWORD` | Oxylabs API password | Required |
| `PORT` | Application port | `8080` |

### Cloud Run Configuration

- **Memory**: 512Mi
- **CPU**: 1 vCPU
- **Max Instances**: 10
- **Region**: us-central1
- **Authentication**: Public (unauthenticated)

## Monitoring

### Logs

View logs in Google Cloud Console:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=youtube-search-api"
```

### Metrics

Monitor the service in Google Cloud Console:
- Request count
- Response time
- Error rate
- Memory usage

## Troubleshooting

### Common Issues

1. **GCS Permission Denied**
   - Ensure the service account has `Storage Object Admin` role
   - Check bucket name and project ID

2. **Oxylabs API Errors**
   - Verify credentials in environment variables
   - Check Oxylabs account status and quotas

3. **Container Build Failures**
   - Ensure Docker is running
   - Check Dockerfile syntax

### Debug Mode

Enable debug logging by setting the log level:

```python
logging.basicConfig(level=logging.DEBUG)
```

## Security Considerations

- Store sensitive credentials in environment variables
- Use IAM roles with minimal required permissions
- Enable Cloud Run's built-in security features
- Consider using Secret Manager for production credentials

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License. 