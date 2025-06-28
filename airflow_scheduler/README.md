# Airflow Scheduler Service

This service provides automated scheduling for the shoe review processing pipeline using Apache Airflow. It allows users to submit batches of shoes for review and automatically processes them through the YouTube search and product summary generation pipeline.

## Features

- **Batch Processing**: Submit multiple shoes for review in a single request
- **Automated Workflow**: Automatically triggers YouTube search, waits for processing, then generates product summaries
- **Job Management**: Monitor job status, list recent jobs, and cancel running jobs
- **Configurable Timing**: Set custom wait times between search and summary generation
- **REST API**: Easy-to-use HTTP endpoints for all operations

## Architecture

The service consists of two main components:

1. **Apache Airflow**: Handles the workflow orchestration and scheduling
2. **FastAPI Service**: Provides REST API endpoints for job management

### Workflow Steps

1. **YouTube Search**: Searches YouTube for reviews of each shoe in the batch
2. **Wait Period**: Waits for the specified time to allow processing to complete
3. **Product Summary Generation**: Triggers the product summary API to generate unified summaries
4. **Completion**: Logs the successful completion of the automation

## API Endpoints

### Schedule Automation
```http
POST /schedule
```

**Request Body:**
```json
{
  "shoes": [
    {
      "name": "Nike Air Jordan 1",
      "max_results": 5
    },
    {
      "name": "Adidas Ultraboost",
      "max_results": 3
    }
  ],
  "wait_minutes": 10
}
```

**Response:**
```json
{
  "job_id": "shoe_review_20250101_120000",
  "status": "scheduled",
  "message": "Successfully scheduled automation for 2 shoes",
  "scheduled_time": "2025-01-01T12:00:00",
  "shoes_count": 2
}
```

### Get Job Status
```http
GET /jobs/{job_id}
```

**Response:**
```json
{
  "job_id": "shoe_review_20250101_120000",
  "status": "running",
  "start_date": "2025-01-01T12:00:00",
  "end_date": null,
  "state": "running",
  "message": "Job running"
}
```

### List Jobs
```http
GET /jobs?limit=10&offset=0
```

### Cancel Job
```http
DELETE /jobs/{job_id}
```

### Health Check
```http
GET /health
```

## Deployment

### Prerequisites

1. Google Cloud Project with billing enabled
2. Google Cloud CLI installed and configured
3. Docker installed
4. Access to Google Container Registry

### Deploy to Google Cloud Run

1. **Update Project ID**: Ensure the `PROJECT_ID` in `deploy.sh` matches your project
2. **Deploy the service**:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

### Environment Variables

The service uses the following environment variables:

- `AIRFLOW_BASE_URL`: URL of the Airflow webserver (default: http://localhost:8080)
- `AIRFLOW_USERNAME`: Airflow username (default: airflow)
- `AIRFLOW_PASSWORD`: Airflow password (default: airflow)

## Usage Examples

### Example 1: Schedule a Single Shoe Review
```bash
curl -X POST "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "shoes": [
      {
        "name": "Nike Air Jordan 1",
        "max_results": 5
      }
    ],
    "wait_minutes": 10
  }'
```

### Example 2: Schedule Multiple Shoes
```bash
curl -X POST "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "shoes": [
      {
        "name": "Nike Air Jordan 1",
        "max_results": 5
      },
      {
        "name": "Adidas Ultraboost",
        "max_results": 3
      },
      {
        "name": "New Balance 990",
        "max_results": 4
      }
    ],
    "wait_minutes": 15
  }'
```

### Example 3: Check Job Status
```bash
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/jobs/shoe_review_20250101_120000"
```

### Example 4: List Recent Jobs
```bash
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/jobs?limit=5"
```

## Integration with Existing Services

The Airflow scheduler integrates with your existing services:

- **YouTube Search API**: `https://youtube-search-api-nxbmt7mfiq-uc.a.run.app/search`
- **Product Summary API**: `https://product-summary-api-nxbmt7mfiq-uc.a.run.app/auto-process`

## Monitoring and Logging

- Job status and progress are logged to Airflow's built-in logging system
- The FastAPI service provides health check endpoints
- All API requests and responses are logged for debugging

## Error Handling

- Failed jobs are automatically retried (configurable retry count)
- API errors are returned with appropriate HTTP status codes
- Detailed error messages help with troubleshooting

## Security Considerations

- The service runs on Google Cloud Run with authentication
- Environment variables should be properly configured for production
- Consider using Google Cloud IAM for additional security

## Troubleshooting

### Common Issues

1. **Airflow Connection Failed**: Check if Airflow is running and accessible
2. **Job Stuck**: Check Airflow logs for detailed error information
3. **API Timeout**: Increase timeout values for long-running jobs

### Debug Commands

```bash
# Check service health
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/health"

# View service logs
gcloud run services logs read airflow-scheduler --region us-central1
```

## Next Steps

After deployment, you can:

1. Test the service with a small batch of shoes
2. Monitor job execution in the Airflow UI
3. Set up automated scheduling for regular batch processing
4. Integrate with your existing monitoring and alerting systems 