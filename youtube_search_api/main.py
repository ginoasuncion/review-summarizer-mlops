from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from dotenv import load_dotenv
import os
import json
from datetime import datetime
from google.cloud import storage
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="YouTube Search API", version="1.0.0")

# GCP Configuration
BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "youtube-search-data-bucket")
PROJECT_ID = os.getenv("GCP_PROJECT_ID")

class SearchRequest(BaseModel):
    query: str
    max_results: int = 20

class SearchResponse(BaseModel):
    status: str
    message: str
    raw_file_path: str
    timestamp: str

def get_oxylabs_credentials():
    """Get Oxylabs credentials from environment."""
    username = os.getenv("OXYLABS_USERNAME")
    password = os.getenv("OXYLABS_PASSWORD")
    
    if not username or not password:
        raise ValueError("Oxylabs credentials not configured")
    
    return username, password

def search_youtube_with_oxylabs(query: str):
    """Search YouTube via Oxylabs API."""
    username, password = get_oxylabs_credentials()
    
    url = 'https://realtime.oxylabs.io/v1/queries'
    payload = {
        'source': 'youtube_search',
        'query': query
    }

    response = requests.post(url, auth=(username, password), json=payload)
    
    if response.status_code != 200:
        logger.error(f"Oxylabs API error: {response.status_code} - {response.text}")
        raise HTTPException(status_code=500, detail=f"Search API failed: {response.status_code}")
    
    return response.json()

def upload_to_gcs(data: dict, query: str) -> str:
    """Upload raw search data to Google Cloud Storage."""
    try:
        # Initialize GCS client
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"raw_data/youtube_search_{query.replace(' ', '_')}_{timestamp}.json"
        
        # Create blob and upload
        blob = bucket.blob(filename)
        blob.upload_from_string(
            json.dumps(data, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
        
        logger.info(f"Uploaded raw data to gs://{BUCKET_NAME}/{filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Failed to upload to GCS: {e}")
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {str(e)}")

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "YouTube Search API"}

@app.post("/search", response_model=SearchResponse)
async def search_youtube(request: SearchRequest):
    """Search YouTube and save raw data to GCS."""
    try:
        logger.info(f"Processing search request: {request.query}")
        
        # Search YouTube
        raw_data = search_youtube_with_oxylabs(request.query)
        
        # Upload to GCS
        file_path = upload_to_gcs(raw_data, request.query)
        
        # Add metadata to response
        response_data = {
            "status": "success",
            "message": f"Search completed for '{request.query}'",
            "raw_file_path": file_path,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Search completed successfully: {file_path}")
        return SearchResponse(**response_data)
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Detailed health check."""
    try:
        # Test GCS connection
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        bucket.reload()
        
        return {
            "status": "healthy",
            "gcs_connection": "ok",
            "oxylabs_configured": bool(os.getenv("OXYLABS_USERNAME") and os.getenv("OXYLABS_PASSWORD"))
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080))) 