# YouTube Data Processor

A Cloud Function that automatically processes YouTube search data and extracts key information for each video. This function is triggered by Cloud Storage events when new search data is uploaded to the source bucket.

## 🚀 Features

- **Automatic Triggering**: Listens to Cloud Storage events for new file uploads
- **Data Processing**: Extracts comprehensive video information from raw search results
- **Search Query Extraction**: Automatically extracts search queries from filenames
- **Structured Output**: Saves processed data in a clean, structured format
- **Error Handling**: Robust error handling and logging
- **Scalable**: Built on Cloud Run for automatic scaling

## 📋 What Gets Processed

For each video in the search results, the processor extracts:

### Basic Information
- Video ID, title, description
- Channel title and ID
- Publication date
- Thumbnails and tags
- Category and language information

### Statistics (if available)
- View count, like count
- Comment count, favorite count

### Content Details (if available)
- Duration, video quality
- Caption availability
- License information

### Status Information (if available)
- Upload and privacy status
- Embedding permissions
- Made for kids flag

## 🏗️ Architecture

```
YouTube Search API → Source Bucket → Cloud Function → Processed Data Bucket
```

1. **YouTube Search API** saves raw search results to `youtube-search-data-bucket`
2. **Cloud Function** is triggered by new file uploads
3. **Data Processing** extracts and structures video information
4. **Processed Data** is saved to `youtube-processed-data-bucket`

## 📁 File Naming Convention

The processor expects source files to follow this naming pattern:
```
search_query_YYYYMMDD_HHMMSS.json
```

Examples:
- `Adidas_Samba_Review_20241201_143022.json`
- `Nike_Air_Max_20241201_143022.json`
- `Best_Running_Shoes_2024_20241201_143022.json`

The search query is automatically extracted from the filename and included in the processed data.

## 🛠️ Setup and Deployment

### Prerequisites

1. Google Cloud Project with billing enabled
2. Google Cloud CLI installed and configured
3. Docker installed
4. Appropriate IAM permissions

### Environment Variables

- `SOURCE_BUCKET`: Source bucket name (default: `youtube-search-data-bucket`)
- `DESTINATION_BUCKET`: Destination bucket name (default: `youtube-processed-data-bucket`)
- `GOOGLE_CLOUD_PROJECT`: Your GCP project ID

### Deployment

1. **Make the deployment script executable:**
   ```bash
   chmod +x deploy.sh
   ```

2. **Run the deployment:**
   ```bash
   ./deploy.sh
   ```

The deployment script will:
- Build and push the Docker image
- Create the destination bucket
- Deploy to Cloud Run
- Set up Cloud Storage triggers
- Configure Pub/Sub notifications

### Manual Deployment

If you prefer manual deployment:

```bash
# Build and push Docker image
IMAGE_NAME="gcr.io/YOUR_PROJECT_ID/youtube-data-processor"
docker build --platform linux/amd64 -t $IMAGE_NAME .
docker push $IMAGE_NAME

# Deploy to Cloud Run
gcloud run deploy youtube-data-processor \
    --image $IMAGE_NAME \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars "SOURCE_BUCKET=youtube-search-data-bucket,DESTINATION_BUCKET=youtube-processed-data-bucket"
```

## 🧪 Testing

### Test Filename Parsing

```bash
python test_filename_parsing.py
```

### Test with Sample Data

1. Upload a sample JSON file to the source bucket
2. Check the processed data in the destination bucket
3. Monitor logs: `gcloud logs tail --service=youtube-data-processor`

## 📊 Output Format

The processed data is saved in this structure:

```json
{
  "search_info": {
    "search_query": "Adidas Samba Review",
    "search_timestamp": "2024-12-01T14:30:22Z",
    "total_results": 1000,
    "results_per_page": 25,
    "source_file": "Adidas_Samba_Review_20241201_143022.json"
  },
  "videos": [
    {
      "video_id": "abc123",
      "title": "Adidas Samba Review 2024",
      "description": "Complete review of the Adidas Samba...",
      "channel_title": "Shoe Review Channel",
      "view_count": 15000,
      "like_count": 500,
      "duration": "PT10M30S",
      "published_at": "2024-01-15T10:00:00Z"
    }
  ],
  "video_count": 25,
  "processing_timestamp": "2024-12-01T14:30:25Z",
  "processing_version": "1.0.0"
}
```

## 🔍 Monitoring

### View Logs
```bash
gcloud logs tail --service=youtube-data-processor --region=us-central1
```

### Check Bucket Contents
```bash
# List processed files
gsutil ls gs://youtube-processed-data-bucket/processed/

# View a processed file
gsutil cat gs://youtube-processed-data-bucket/processed/filename.json
```

## 🔧 Troubleshooting

### Common Issues

1. **Function not triggering**: Check Cloud Storage notifications and Pub/Sub subscriptions
2. **Permission errors**: Ensure the service account has Storage Object Admin permissions
3. **Processing errors**: Check logs for specific error messages
4. **Missing data**: Verify the source file format matches expected structure

### Debug Mode

Enable debug logging by setting the log level in the function:
```python
logging.basicConfig(level=logging.DEBUG)
```

## 📈 Performance

- **Memory**: 1GB allocated
- **CPU**: 1 vCPU
- **Timeout**: 300 seconds
- **Concurrency**: 80 requests per instance
- **Max Instances**: 10 (auto-scaling)

## 🔄 Version History

- **v1.0.0**: Initial release with basic video data extraction
- Added search query extraction from filenames
- Comprehensive error handling and logging
- Cloud Storage trigger integration

## 📝 License

This project is part of the Review Summarizer MLOps pipeline. 