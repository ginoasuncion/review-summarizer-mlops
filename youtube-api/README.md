# YouTube Search API

A Cloud Run service that searches YouTube via Oxylabs API and saves raw data to Google Cloud Storage.

## 🏗️ Architecture

```
HTTP Request → Cloud Run API → Oxylabs API → GCS Bucket
```

## 📁 Project Structure

```
youtube-api/
├── src/
│   └── main.py              # FastAPI application
├── deployment/
│   ├── cloudbuild.yaml      # Cloud Build configuration
│   ├── setup.sh            # GCP infrastructure setup
│   └── deploy.sh           # Deployment script
├── requirements.txt         # Python dependencies
├── Dockerfile              # Container configuration
├── env.example             # Environment variables template
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Setup GCP Infrastructure

```bash
cd youtube-api
chmod +x deployment/setup.sh
./deployment/setup.sh YOUR_PROJECT_ID
```

This will:
- Enable required GCP APIs
- Create GCS bucket
- Create service account with proper permissions
- Generate service account key for local development

### 2. Deploy to Cloud Run

```bash
chmod +x deployment/deploy.sh
./deployment/deploy.sh YOUR_PROJECT_ID
```

This will:
- Build and deploy the container
- Prompt for Oxylabs credentials
- Set environment variables
- Return the service URL

## 🔧 Local Development

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables

```bash
cp env.example .env
# Edit .env with your actual values
```

### 3. Set Service Account Key

```bash
export GOOGLE_APPLICATION_CREDENTIALS=./youtube-api-key.json
```

### 4. Run Locally

```bash
python src/main.py
```

## 📡 API Endpoints

### Health Check
```bash
GET /
```

### Search YouTube
```bash
POST /search
Content-Type: application/json

{
  "query": "tesla model 3 review",
  "max_results": 20
}
```

### Detailed Health Check
```bash
GET /health
```

## 🔐 Authentication & Permissions

### Service Account
The service uses a dedicated service account (`youtube-api-sa`) with:
- `roles/storage.objectViewer` - Read from GCS
- `roles/storage.objectCreator` - Write to GCS
- `roles/run.invoker` - Cloud Run permissions

### Environment Variables
- `GCP_PROJECT_ID` - Your GCP project ID
- `GCP_BUCKET_NAME` - GCS bucket name (default: youtube-data-pipeline)
- `OXYLABS_USERNAME` - Oxylabs API username
- `OXYLABS_PASSWORD` - Oxylabs API password

## 📊 Data Flow

1. **HTTP Request** → Cloud Run service
2. **Search** → Oxylabs YouTube API
3. **Process** → Parse and validate response
4. **Store** → Upload raw JSON to GCS bucket
5. **Response** → Return file path and metadata

## 🗂️ GCS File Structure

```
gs://youtube-data-pipeline/
└── raw_data/
    └── youtube_search_{query}_{timestamp}.json
```

## 🛠️ Troubleshooting

### Common Issues

1. **Service Account Not Found**
   ```bash
   ./deployment/setup.sh YOUR_PROJECT_ID
   ```

2. **Permission Denied**
   - Check service account permissions
   - Verify bucket exists and is accessible

3. **Oxylabs API Errors**
   - Verify credentials in environment variables
   - Check Oxylabs account status

### Logs
```bash
gcloud logs read --service=youtube-search-api --limit=50
```

## 🔄 Next Steps

This API is designed to be part of a larger data pipeline:

1. **Raw Data** → This API saves to GCS
2. **Parsing** → Cloud Function processes raw data
3. **Transcripts** → Cloud Function fetches transcripts
4. **BigQuery** → Data stored in staging/production tables

## 📝 License

This project is part of the review-summarizer-mlops pipeline. 