import json
import os
from google.cloud import bigquery
from google.cloud import storage

def gcs_to_bq(event, context):
    """Triggered by a change to a GCS bucket. Loads a new log file into BigQuery."""
    PROJECT_ID = "buoyant-yew-463209-k5"
    DATASET = "youtube_reviews"
    TABLE = "search_logs"
    table_id = f"{PROJECT_ID}.{DATASET}.{TABLE}"

    bucket_name = event['bucket']
    file_name = event['name']

    # Only process .json files in query_logs/
    if not file_name.startswith("query_logs/") or not file_name.endswith(".json"):
        print(f"Skipping file: {file_name}")
        return

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)
    content = blob.download_as_text().strip()

    # Skip empty files
    if not content:
        print(f"Empty file: {file_name}, skipping.")
        return

    # Try to parse JSON, attempt to fix common issues
    try:
        log_entry = json.loads(content)
    except Exception as e:
        # Try to fix common issues: remove trailing commas, fix partial objects
        try:
            fixed_content = content.rstrip(',\n')
            log_entry = json.loads(fixed_content)
            print(f"Fixed minor JSON issue in {file_name}.")
        except Exception as e2:
            print(f"Invalid JSON in {file_name}: {e2}")
            return  # Skip invalid file

    # Validate required fields
    required_fields = ["timestamp", "product_name", "found_in_bigquery", "status"]
    if not all(field in log_entry for field in required_fields):
        print(f"Missing required fields in {file_name}: {log_entry}")
        return  # Skip file with missing fields

    # Prepare row for BigQuery
    row = [{
        "timestamp": log_entry["timestamp"],
        "product_name": log_entry["product_name"],
        "found_in_bigquery": log_entry["found_in_bigquery"],
        "status": log_entry["status"]
    }]
    try:
        bq_client = bigquery.Client(project=PROJECT_ID)
        errors = bq_client.insert_rows_json(table_id, row)
        if errors:
            print(f"BigQuery insert errors for {file_name}: {errors}")
        else:
            print(f"Inserted log from {file_name} into BigQuery.")
    except Exception as e:
        print(f"Error inserting {file_name} into BigQuery: {e}") 