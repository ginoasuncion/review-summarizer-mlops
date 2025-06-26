from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.cloud import bigquery
from datetime import datetime
import os

app = FastAPI(title="Search Log API", version="1.0.0")

# BigQuery configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-gcp-project")
DATASET = os.environ.get("BIGQUERY_DATASET", "your_dataset")
TABLE = os.environ.get("BIGQUERY_TABLE", "search_logs")

bq_client = bigquery.Client(project=PROJECT_ID)

class SearchLog(BaseModel):
    timestamp: datetime
    product_name: str
    found_in_bigquery: bool
    status: str

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "search-log-api"}

@app.post("/log")
def log_search_event(log: SearchLog):
    try:
        table_id = f"{PROJECT_ID}.{DATASET}.{TABLE}"
        row = [
            {
                "timestamp": log.timestamp.isoformat(),
                "product_name": log.product_name,
                "found_in_bigquery": log.found_in_bigquery,
                "status": log.status
            }
        ]
        errors = bq_client.insert_rows_json(table_id, row)
        if errors:
            raise Exception(f"BigQuery insert errors: {errors}")
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080))) 