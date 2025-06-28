# YouTube Review Summarizer - MLOps Pipeline

A comprehensive MLOps pipeline that automatically searches YouTube for shoe reviews, processes transcripts, generates summaries, and provides unified product insights using LLM evaluation.

## 🏗️ Architecture Overview

```
YouTube Search API → Data Processing → Transcript Processing → 
LLM Summarization → LLM Evaluation → Product Aggregation → Query API
```

## 🚀 Services

### Core Services
- **YouTube Search API** - Searches YouTube for review videos
- **YouTube Data Processor** - Processes video metadata and triggers transcript processing
- **YouTube Transcript Processor** - Downloads and processes video transcripts
- **YouTube Transcript Summarizer** - Generates video summaries using OpenAI
- **LLM Judge API** - Evaluates summary quality using LLM scoring
- **Product Summary API** - Aggregates video summaries into product summaries
- **Product Query API** - Provides query interface for product summaries
- **Airflow Scheduler** - Orchestrates batch processing workflows

### Infrastructure
- **Google Cloud Run** - Containerized services
- **Google Cloud Storage** - File storage for transcripts and data
- **BigQuery** - Data warehouse for metadata, summaries, and scores
- **Pub/Sub** - Event-driven processing
- **Cloud Functions** - Serverless processing triggers

## 📊 Data Flow

1. **Search Phase**: YouTube Search API finds review videos
2. **Processing Phase**: Videos are processed through transcript extraction
3. **Summarization Phase**: Transcripts are summarized using OpenAI
4. **Evaluation Phase**: LLM Judge evaluates summary quality
5. **Aggregation Phase**: Product Summary API creates unified summaries
6. **Query Phase**: Product Query API provides access to results

## 🛠️ Setup & Deployment

### Prerequisites
- Google Cloud Project with billing enabled
- Google Cloud CLI installed and configured
- Docker installed
- OpenAI API key

### Environment Variables
Set these environment variables for each service:
```bash
export OPENAI_API_KEY="your-openai-api-key"
export GOOGLE_CLOUD_PROJECT="buoyant-yew-463209-k5"
```

### Deployment
Each service can be deployed using its respective `deploy.sh` script:
```bash
cd <service-directory>
chmod +x deploy.sh
./deploy.sh
```

## 📡 API Reference

### YouTube Search API
**Endpoint**: `https://youtube-search-api-nxbmt7mfiq-uc.a.run.app/search`

```bash
curl -X POST "https://youtube-search-api-nxbmt7mfiq-uc.a.run.app/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Nike Air Jordan 1 review",
    "max_results": 5
  }'
```

### Product Summary API
**Endpoint**: `https://product-summary-api-nxbmt7mfiq-uc.a.run.app/auto-process`

```bash
curl -X POST "https://product-summary-api-nxbmt7mfiq-uc.a.run.app/auto-process"
```

### Product Query API
**Endpoint**: `https://product-query-api-nxbmt7mfiq-uc.a.run.app/query`

```bash
curl -X POST "https://product-query-api-nxbmt7mfiq-uc.a.run.app/query" \
  -H "Content-Type: application/json" \
  -d '{
    "product_name": "Nike Air Jordan 1"
  }'
```

### Airflow Scheduler API
**Base URL**: `https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app`

#### Health Check
```bash
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/health"
```

#### Schedule Automation
```bash
curl -X POST "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "shoes": [
      {"name": "Nike Air Jordan 1", "max_results": 5},
      {"name": "Adidas Ultraboost", "max_results": 3}
    ],
    "wait_minutes": 10
  }'
```

#### Job Management
```bash
# Check job status
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/jobs/{job_id}"

# List jobs
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/jobs?limit=10"

# Cancel job
curl -X DELETE "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/jobs/{job_id}"
```

## 🗄️ Database Schema

### BigQuery Tables

#### `youtube_reviews.video_metadata`
- `video_id` (STRING) - YouTube video ID
- `title` (STRING) - Video title
- `channel_title` (STRING) - Channel name
- `description` (STRING) - Video description
- `published_at` (TIMESTAMP) - Publication date
- `view_count` (INTEGER) - View count
- `like_count` (INTEGER) - Like count
- `comment_count` (INTEGER) - Comment count
- `duration` (STRING) - Video duration
- `tags` (REPEATED STRING) - Video tags
- `search_query` (STRING) - Original search query
- `summary_available` (BOOLEAN) - Whether summary exists
- `llm_relevance_score` (FLOAT) - LLM relevance score
- `llm_helpfulness_score` (FLOAT) - LLM helpfulness score
- `llm_conciseness_score` (FLOAT) - LLM conciseness score
- `processed_at` (TIMESTAMP) - Processing timestamp
- `summary_content` (STRING) - Generated summary

#### `youtube_reviews.product_summaries`
- `product_name` (STRING) - Product name
- `total_reviews` (INTEGER) - Number of reviews
- `total_views` (INTEGER) - Total view count
- `average_views` (FLOAT) - Average views per review
- `summary_content` (STRING) - Unified product summary
- `created_at` (TIMESTAMP) - Creation timestamp

#### `youtube_reviews.llm_scores`
- `video_id` (STRING) - YouTube video ID
- `product_name` (STRING) - Product name
- `relevance_score` (FLOAT) - Relevance score
- `helpfulness_score` (FLOAT) - Helpfulness score
- `conciseness_score` (FLOAT) - Conciseness score
- `overall_score` (FLOAT) - Overall score
- `evaluation_date` (TIMESTAMP) - Evaluation timestamp

## 📈 Monitoring & Analytics

### BigQuery Queries

#### Check Recent Videos
```sql
SELECT video_id, title, search_query, processed_at 
FROM `buoyant-yew-463209-k5.youtube_reviews.video_metadata` 
ORDER BY processed_at DESC 
LIMIT 10
```

#### Check Product Summaries
```sql
SELECT product_name, total_reviews, created_at 
FROM `buoyant-yew-463209-k5.youtube_reviews.product_summaries` 
ORDER BY created_at DESC
```

#### LLM Score Analysis
```sql
SELECT 
  product_name,
  AVG(relevance_score) as avg_relevance,
  AVG(helpfulness_score) as avg_helpfulness,
  AVG(conciseness_score) as avg_conciseness,
  COUNT(*) as evaluations
FROM `buoyant-yew-463209-k5.youtube_reviews.llm_scores`
GROUP BY product_name
ORDER BY avg_relevance DESC
```

### Grafana Dashboards

Set up Grafana dashboards for:
- **Success Rate Monitoring**: Query logs success/failure rates
- **LLM Score Tracking**: Video and product-level scores over time
- **Processing Metrics**: Video processing throughput and latency
- **Error Monitoring**: Failed processing attempts and error rates

## 🔄 Workflow Examples

### Manual Processing
```bash
# 1. Search for videos
curl -X POST "https://youtube-search-api-nxbmt7mfiq-uc.a.run.app/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "Vans Old Skool review", "max_results": 5}'

# 2. Wait for processing (10-15 minutes)

# 3. Generate product summary
curl -X POST "https://product-summary-api-nxbmt7mfiq-uc.a.run.app/auto-process"

# 4. Query results
curl -X POST "https://product-query-api-nxbmt7mfiq-uc.a.run.app/query" \
  -H "Content-Type: application/json" \
  -d '{"product_name": "Vans Old Skool"}'
```

### Automated Processing
```bash
# Schedule batch processing
curl -X POST "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "shoes": [
      {"name": "Vans Old Skool", "max_results": 5},
      {"name": "Reebok Classic", "max_results": 3},
      {"name": "Puma Suede", "max_results": 4}
    ],
    "wait_minutes": 10
  }'
```

## 🧪 Testing

### Test Individual Services
```bash
# Test YouTube Search
curl "https://youtube-search-api-nxbmt7mfiq-uc.a.run.app/"

# Test Product Summary
curl -X POST "https://product-summary-api-nxbmt7mfiq-uc.a.run.app/auto-process"

# Test Product Query
curl -X POST "https://product-query-api-nxbmt7mfiq-uc.a.run.app/query" \
  -H "Content-Type: application/json" \
  -d '{"product_name": "Nike Air Jordan 1"}'

# Test Airflow Scheduler
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/health"
```

### Test Complete Workflow
```bash
# 1. Schedule a test job
curl -X POST "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/schedule" \
  -H "Content-Type: application/json" \
  -d '{
    "shoes": [{"name": "Test Shoe", "max_results": 2}],
    "wait_minutes": 5
  }'

# 2. Monitor job progress
curl "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app/jobs/{job_id}"

# 3. Check database results
bq query --use_legacy_sql=false "
SELECT * FROM \`buoyant-yew-463209-k5.youtube_reviews.video_metadata\` 
WHERE search_query = 'Test Shoe review'"
```

## 🚨 Troubleshooting

### Common Issues

1. **Service Not Starting**
   - Check Cloud Run logs: `gcloud run services logs read <service-name> --region us-central1`
   - Verify environment variables are set
   - Check Docker image builds successfully

2. **Processing Failures**
   - Check BigQuery for error logs
   - Verify OpenAI API key is valid
   - Check Cloud Storage permissions

3. **Missing Transcripts**
   - Verify video has captions available
   - Check transcript processor logs
   - Ensure video is not age-restricted

4. **LLM Score Issues**
   - Verify LLM Judge API is running
   - Check OpenAI API quota and limits
   - Review evaluation prompts

### Debug Commands
```bash
# Check service logs
gcloud run services logs read youtube-search-api --region us-central1
gcloud run services logs read product-summary-api --region us-central1
gcloud run services logs read airflow-scheduler --region us-central1

# Check BigQuery data
bq query --use_legacy_sql=false "
SELECT COUNT(*) as total_videos 
FROM \`buoyant-yew-463209-k5.youtube_reviews.video_metadata\`"

# Check Cloud Storage
gsutil ls gs://youtube-reviews-bucket/
```

## 📝 Configuration

### Service Configuration
Each service can be configured via environment variables:

- `OPENAI_API_KEY` - OpenAI API key for LLM operations
- `GOOGLE_CLOUD_PROJECT` - Google Cloud project ID
- `BIGQUERY_DATASET` - BigQuery dataset name
- `GCS_BUCKET` - Cloud Storage bucket name

### Scaling Configuration
- **YouTube Search API**: 1-10 instances
- **Data Processor**: 1-5 instances  
- **Transcript Processor**: 1-20 instances
- **Summarizer**: 1-10 instances
- **LLM Judge**: 1-5 instances
- **Product APIs**: 1-10 instances

## 🔐 Security

- All services run on Google Cloud Run with authentication
- Environment variables are encrypted
- API keys are stored securely
- BigQuery access is controlled via IAM
- Cloud Storage buckets have appropriate permissions

## 📈 Performance

### Current Metrics
- **Processing Time**: 5-15 minutes per video
- **Throughput**: 10-50 videos per hour
- **Accuracy**: 85-95% transcript extraction success
- **LLM Evaluation**: 2-5 seconds per summary

### Optimization Tips
- Use appropriate `max_results` for search queries
- Batch process multiple shoes together
- Monitor Cloud Run instance scaling
- Optimize BigQuery query patterns

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review service logs
3. Check BigQuery for data issues
4. Verify API endpoints are responding

---

**Last Updated**: June 2025
**Version**: 1.0.0
**Status**: Production Ready 