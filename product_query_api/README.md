# Product Query API

A Flask-based API that allows users to query product summaries from BigQuery and logs all queries to Cloud Storage.

## Features

- **Product Query**: Search for existing product summaries in BigQuery
- **Query Logging**: Log all queries (successful and unsuccessful) to Cloud Storage
- **Log Analytics**: View and analyze query logs with filtering and statistics
- **Product Search**: Search for products with partial matching
- **Statistics**: Get statistics about stored products
- **MVP Version**: No pipeline triggering - only querying and logging

## Endpoints

### POST /query
Query a product summary from BigQuery.

**Request:**
```json
{
  "product_name": "Adidas Ultraboost"
}
```

**Response (Found):**
```json
{
  "status": "found",
  "message": "Product summary found for \"Adidas Ultraboost\"",
  "data": {
    "product_name": "Adidas Ultraboost Review",
    "search_query": "raw data/youtube search Adidas Ultraboost review",
    "summary_content": "...",
    "total_reviews": 20,
    "total_views": 0,
    "average_views": 0.0,
    "processed_at": "2025-06-24T23:30:09.665943+00:00",
    "found_in_bigquery": true
  },
  "source": "bigquery"
}
```

**Response (Not Found):**
```json
{
  "status": "not_found",
  "message": "Product \"Nike Air Max\" not found in database.",
  "note": "Query has been logged. Pipeline triggering not available in MVP version."
}
```

### GET /search?q=<query>
Search for products with partial matching.

**Example:**
```
GET /search?q=adidas
```

**Response:**
```json
{
  "query": "adidas",
  "total_results": 2,
  "products": [
    {
      "product_name": "Adidas Ultraboost Review",
      "search_query": "raw data/youtube search Adidas Ultraboost review",
      "summary_content": "Product Overview: The Adidas Ultraboost...",
      "total_reviews": 20,
      "total_views": 0,
      "average_views": 0.0,
      "processed_at": "2025-06-24T23:30:09.665943+00:00"
    }
  ]
}
```

### GET /logs
View query logs from Cloud Storage.

**Query Parameters:**
- `limit` (optional): Number of logs to return (default: 10, max: 50)
- `status` (optional): Filter by status - `success`, `not_found`, or leave empty for all

**Example:**
```
GET /logs?limit=5&status=success
```

**Response:**
```json
{
  "total_logs": 2,
  "requested_limit": 5,
  "status_filter": "success",
  "logs": [
    {
      "filename": "query_logs/20250625_000610_Adidas_Ultraboost_found.json",
      "found_in_bigquery": true,
      "product_name": "Adidas Ultraboost",
      "status": "success",
      "summary_data": {
        "processed_at": "2025-06-24T23:30:09.373760+00:00",
        "product_name": "Adidas Ultraboost Review",
        "total_reviews": 20
      },
      "timestamp": "2025-06-25T00:06:10.637562+00:00",
      "user_agent": "curl/8.7.1",
      "user_ip": "169.254.169.126"
    }
  ]
}
```

### GET /logs/stats
Get statistics about query logs.

**Response:**
```json
{
  "total_queries": 4,
  "found_count": 2,
  "not_found_count": 2,
  "success_rate": 50.0,
  "top_queried_products": [
    {
      "product": "Adidas Ultraboost",
      "count": 2
    },
    {
      "product": "Nike Air Max 3000",
      "count": 2
    }
  ],
  "timestamp": "2025-06-25T00:08:46.425358+00:00"
}
```

### GET /stats
Get statistics about stored products.

**Response:**
```json
{
  "total_products": 2,
  "recent_products": [
    {
      "product_name": "Adidas Ultraboost Review",
      "processed_at": "2025-06-24T23:30:09.665943+00:00",
      "total_reviews": 20
    }
  ],
  "timestamp": "2025-06-24T23:55:00.000000+00:00"
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "service": "product-query-api",
  "status": "healthy",
  "timestamp": "2025-06-24T23:55:00.000000+00:00",
  "bigquery_table": "buoyant-yew-463209-k5.youtube_reviews.product_summaries",
  "version": "mvp"
}
```

## Query Logging

All queries are logged to Cloud Storage in the `query_logs/` folder with the following structure:

**Filename:** `YYYYMMDD_HHMMSS_product_name_found.json` or `YYYYMMDD_HHMMSS_product_name_not_found.json`

**Log Entry:**
```json
{
  "timestamp": "2025-06-24T23:55:00.000000+00:00",
  "product_name": "Adidas Ultraboost",
  "found_in_bigquery": true,
  "user_ip": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "request_id": "",
  "status": "success",
  "summary_data": {
    "product_name": "Adidas Ultraboost Review",
    "total_reviews": 20,
    "processed_at": "2025-06-24T23:30:09.665943+00:00"
  }
}
```

## Environment Variables

- `GCP_PROJECT_ID`: Google Cloud Project ID (default: buoyant-yew-463209-k5)
- `BIGQUERY_DATASET`: BigQuery dataset name (default: youtube_reviews)
- `BIGQUERY_PROJECT`: BigQuery project ID (default: GCP_PROJECT_ID)
- `QUERY_LOGS_BUCKET`: Cloud Storage bucket for query logs (default: youtube-processed-data-bucket)

## Deployment

```bash
./deploy.sh
```

## Usage Examples

### Query a product
```bash
curl -X POST "https://product-query-api-nxbmt7mfiq-uc.a.run.app/query" \
  -H "Content-Type: application/json" \
  -d '{"product_name": "Adidas Ultraboost"}'
```

### Search for products
```bash
curl "https://product-query-api-nxbmt7mfiq-uc.a.run.app/search?q=adidas"
```

### Get statistics
```bash
curl "https://product-query-api-nxbmt7mfiq-uc.a.run.app/stats"
```

### View query logs
```bash
# Get all logs (up to 10)
curl "https://product-query-api-nxbmt7mfiq-uc.a.run.app/logs"

# Get only successful queries
curl "https://product-query-api-nxbmt7mfiq-uc.a.run.app/logs?status=success"

# Get last 5 not found queries
curl "https://product-query-api-nxbmt7mfiq-uc.a.run.app/logs?status=not_found&limit=5"
```

### Get log statistics
```bash
curl "https://product-query-api-nxbmt7mfiq-uc.a.run.app/logs/stats"
``` 