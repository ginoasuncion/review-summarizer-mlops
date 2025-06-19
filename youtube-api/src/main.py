import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from google.cloud import bigquery, storage
from pydantic import BaseModel

from .youtube_search import YouTubeSearcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI(title="YouTube Search API", version="1.0.0")

# Initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET_NAME = os.environ.get("GCP_BUCKET_NAME", "youtube-data-pipeline")
PARSED_BUCKET_NAME = f"{BUCKET_NAME}-parsed"
TRANSCRIPTS_BUCKET_NAME = f"{BUCKET_NAME}-transcripts"
DATASET_ID = "youtube_data"


class SearchRequest(BaseModel):
    query: str
    max_results: int = 10


class SearchResponse(BaseModel):
    status: str
    message: str
    data: Optional[List[Dict[str, Any]]] = None
    files_saved: Optional[List[str]] = None


class VideoInfo(BaseModel):
    video_id: str
    title: str
    channel_name: str
    views: int
    duration: str
    published_date: str
    thumbnail_url: str
    watch_url: str
    transcript_available: bool = False


class TranscriptInfo(BaseModel):
    video_id: str
    full_text: str
    word_count: int
    language: str
    duration_seconds: float
    is_auto_generated: bool


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

    url = "https://realtime.oxylabs.io/v1/queries"
    payload = {"source": "youtube_search", "query": query}

    response = requests.post(url, auth=(username, password), json=payload)

    if response.status_code != 200:
        logger.error(f"Oxylabs API error: {response.status_code} - {response.text}")
        raise HTTPException(
            status_code=500, detail=f"Search API failed: {response.status_code}"
        )

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
            content_type="application/json",
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
async def search_youtube(request: SearchRequest, background_tasks: BackgroundTasks):
    """Search YouTube and save raw data to GCS"""
    try:
        searcher = YouTubeSearcher()
        results = searcher.search(request.query, request.max_results)

        if not results:
            return SearchResponse(
                status="success", message="No results found", data=[], files_saved=[]
            )

        # Save each video as separate file
        saved_files = []
        for video in results:
            video_id = video.get("videoId")
            if video_id:
                # Add search query to video data
                video["search_query"] = request.query

                # Save to GCS
                bucket = storage_client.bucket(BUCKET_NAME)
                blob_name = f"raw/{video_id}.json"
                blob = bucket.blob(blob_name)
                blob.upload_from_string(
                    json.dumps(video, indent=2), content_type="application/json"
                )
                saved_files.append(f"gs://{BUCKET_NAME}/{blob_name}")

        return SearchResponse(
            status="success",
            message=f"Found {len(results)} videos and saved to GCS",
            data=results,
            files_saved=saved_files,
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/videos", response_model=List[VideoInfo])
async def list_processed_videos(
    limit: int = 50, offset: int = 0, has_transcript: Optional[bool] = None
):
    """List all processed videos with optional transcript filter"""
    try:
        # Query BigQuery staging table
        query = f"""
        SELECT 
            video_id,
            title,
            channel_name,
            views,
            duration,
            published_date,
            thumbnail_url,
            watch_url,
            transcript_available
        FROM `{PROJECT_ID}.{DATASET_ID}.staging_videos`
        """

        if has_transcript is not None:
            query += f" WHERE transcript_available = {has_transcript}"

        query += f" ORDER BY processed_at DESC LIMIT {limit} OFFSET {offset}"

        query_job = bigquery_client.query(query)
        results = query_job.result()

        videos = []
        for row in results:
            videos.append(
                VideoInfo(
                    video_id=row.video_id,
                    title=row.title,
                    channel_name=row.channel_name,
                    views=row.views or 0,
                    duration=row.duration or "",
                    published_date=row.published_date or "",
                    thumbnail_url=row.thumbnail_url or "",
                    watch_url=row.watch_url or "",
                    transcript_available=row.transcript_available or False,
                )
            )

        return videos

    except Exception as e:
        logger.error(f"Error listing videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/videos/{video_id}", response_model=Dict[str, Any])
async def get_video_details(video_id: str):
    """Get detailed information about a specific video"""
    try:
        # Get video info from BigQuery
        query = f"""
        SELECT *
        FROM `{PROJECT_ID}.{DATASET_ID}.staging_videos`
        WHERE video_id = '{video_id}'
        """

        query_job = bigquery_client.query(query)
        results = list(query_job.result())

        if not results:
            raise HTTPException(status_code=404, detail="Video not found")

        video_data = dict(results[0])

        # Check if transcript exists
        if video_data.get("transcript_available"):
            try:
                # Get transcript from GCS
                bucket = storage_client.bucket(TRANSCRIPTS_BUCKET_NAME)
                blob = bucket.blob(f"transcripts/{video_id}.json")
                transcript_content = blob.download_as_text()
                transcript_data = json.loads(transcript_content)
                video_data["transcript"] = transcript_data
            except Exception as e:
                logger.warning(f"Could not load transcript for {video_id}: {e}")
                video_data["transcript"] = None
        else:
            video_data["transcript"] = None

        return video_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/videos/{video_id}/transcript", response_model=TranscriptInfo)
async def get_video_transcript(video_id: str):
    """Get transcript for a specific video"""
    try:
        # Check if transcript exists in BigQuery
        query = f"""
        SELECT 
            video_id,
            full_text,
            word_count,
            language,
            duration_seconds,
            is_auto_generated
        FROM `{PROJECT_ID}.{DATASET_ID}.video_transcripts`
        WHERE video_id = '{video_id}'
        """

        query_job = bigquery_client.query(query)
        results = list(query_job.result())

        if not results:
            raise HTTPException(status_code=404, detail="Transcript not found")

        row = results[0]
        return TranscriptInfo(
            video_id=row.video_id,
            full_text=row.full_text,
            word_count=row.word_count,
            language=row.language,
            duration_seconds=row.duration_seconds,
            is_auto_generated=row.is_auto_generated,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting transcript: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search/videos")
async def search_processed_videos(
    query: str, limit: int = 20, has_transcript: Optional[bool] = None
):
    """Search through processed videos by title, channel, or transcript content"""
    try:
        # Build search query
        search_conditions = []

        # Search in title and channel name
        search_conditions.append(
            f"""
        (LOWER(title) LIKE '%{query.lower()}%' OR 
         LOWER(channel_name) LIKE '%{query.lower()}%')
        """
        )

        # If has_transcript filter is specified
        if has_transcript is not None:
            search_conditions.append(f"transcript_available = {has_transcript}")

        where_clause = " AND ".join(search_conditions)

        sql_query = f"""
        SELECT 
            v.video_id,
            v.title,
            v.channel_name,
            v.views,
            v.duration,
            v.published_date,
            v.thumbnail_url,
            v.watch_url,
            v.transcript_available,
            t.full_text as transcript_preview
        FROM `{PROJECT_ID}.{DATASET_ID}.staging_videos` v
        LEFT JOIN `{PROJECT_ID}.{DATASET_ID}.video_transcripts` t 
            ON v.video_id = t.video_id
        WHERE {where_clause}
        ORDER BY v.views DESC
        LIMIT {limit}
        """

        query_job = bigquery_client.query(sql_query)
        results = query_job.result()

        videos = []
        for row in results:
            video = {
                "video_id": row.video_id,
                "title": row.title,
                "channel_name": row.channel_name,
                "views": row.views or 0,
                "duration": row.duration or "",
                "published_date": row.published_date or "",
                "thumbnail_url": row.thumbnail_url or "",
                "watch_url": row.watch_url or "",
                "transcript_available": row.transcript_available or False,
                "transcript_preview": (
                    row.transcript_preview[:200] + "..."
                    if row.transcript_preview
                    else None
                ),
            }
            videos.append(video)

        return {"query": query, "total_results": len(videos), "videos": videos}

    except Exception as e:
        logger.error(f"Error searching videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_pipeline_stats():
    """Get statistics about the data pipeline"""
    try:
        # Get video count
        video_query = f"""
        SELECT COUNT(*) as total_videos,
               COUNTIF(transcript_available = TRUE) as videos_with_transcripts
        FROM `{PROJECT_ID}.{DATASET_ID}.staging_videos`
        """

        video_job = bigquery_client.query(video_query)
        video_stats = list(video_job.result())[0]

        # Get transcript count
        transcript_query = f"""
        SELECT COUNT(*) as total_transcripts,
               COUNTIF(is_auto_generated = TRUE) as auto_generated,
               COUNTIF(is_auto_generated = FALSE) as manual
        FROM `{PROJECT_ID}.{DATASET_ID}.video_transcripts`
        """

        transcript_job = bigquery_client.query(transcript_query)
        transcript_stats = list(transcript_job.result())[0]

        # Calculate coverage percentage
        coverage_pct = (
            video_stats.videos_with_transcripts / video_stats.total_videos * 100
            if video_stats.total_videos > 0
            else 0
        )

        return {
            "total_videos": video_stats.total_videos,
            "videos_with_transcripts": video_stats.videos_with_transcripts,
            "total_transcripts": transcript_stats.total_transcripts,
            "auto_generated_transcripts": transcript_stats.auto_generated,
            "manual_transcripts": transcript_stats.manual,
            "transcript_coverage": f"{coverage_pct:.1f}%",
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
