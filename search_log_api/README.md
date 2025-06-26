# Search Log API

A minimal FastAPI service for logging product search events to BigQuery.

## Features
- POST /log endpoint to log search events
- Health check endpoint
- Writes to a BigQuery table with schema: timestamp, product_name, found_in_bigquery, status

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   - `GCP_PROJECT_ID`: Your GCP project ID
   - `BIGQUERY_DATASET`: BigQuery dataset name
   - `BIGQUERY_TABLE`: BigQuery table name (default: `search_logs`)

3. Run the API:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8080
   ```

## Endpoints

### Health Check
- `GET /health`

### Log Search Event
- `POST /log`
- **Request Body:**
  ```json
  {
    "timestamp": "2025-06-25T10:14:02.746833+00:00",
    "product_name": "Veja Esplar",
    "found_in_bigquery": false,
    "status": "not_found"
  }
  ```
- **Response:**
  ```json
  { "status": "success" }
  ```

## BigQuery Table Schema

- `timestamp` (TIMESTAMP, REQUIRED)
- `product_name` (STRING, REQUIRED)
- `found_in_bigquery` (BOOL, REQUIRED)
- `status` (STRING, REQUIRED) 