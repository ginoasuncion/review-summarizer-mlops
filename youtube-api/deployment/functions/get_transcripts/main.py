import logging
import os
from datetime import datetime, timezone
from typing import Optional

import functions_framework
import requests
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

# Configuration
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET_NAME = os.environ.get("GCP_BUCKET_NAME", "youtube-data-pipeline")
DATASET_ID = "youtube_data"
STAGING_TABLE_ID = "staging_video_metadata"
TRANSCRIPTS_TABLE_ID = "staging_video_transcripts"
TRANSCRIPTS_BUCKET_NAME = f"{BUCKET_NAME}-transcripts"

# Oxylabs credentials
OXYLABS_USERNAME = os.environ.get("OXYLABS_USERNAME")
OXYLABS_PASSWORD = os.environ.get("OXYLABS_PASSWORD")


def get_video_transcript_text(video_id: str) -> Optional[str]:
    """Fetch transcript for a YouTube video using Oxylabs"""
    try:
        if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
            logger.error("Oxylabs credentials not configured")
            return None

        payload = {
            "source": "youtube_transcript",
            "query": video_id,
            "context": [
                {"key": "language_code", "value": "en"},
                {"key": "transcript_origin", "value": "auto_generated"},
            ],
        }

        response = requests.post(
            "https://realtime.oxylabs.io/v1/queries",
            auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            logger.error(f"Oxylabs request failed: {response.status_code}")
            return None

        data = response.json()
        if "results" not in data or not data["results"]:
            logger.error("No results from Oxylabs")
            return None

        result = data["results"][0]
        if "content" in result and result["content"]:
            transcript_text = parse_transcript_segments(result["content"])
            if transcript_text:
                logger.info(f"Successfully fetched transcript for video {video_id}")
                return transcript_text
            else:
                logger.warning(f"No transcript text extracted for video {video_id}")
                return None
        else:
            logger.warning(
                f"No transcript content found in Oxylabs response for video {video_id}"
            )
            return None

    except Exception as e:
        logger.error(f"Error fetching transcript for video {video_id}: {e}")
        return None


def parse_transcript_segments(content: list) -> Optional[str]:
    """Parse transcript segments from Oxylabs response"""
    try:
        transcript_lines = []
        for segment in content:
            if "transcriptSegmentRenderer" in segment:
                renderer = segment["transcriptSegmentRenderer"]
                if "snippet" in renderer and "runs" in renderer["snippet"]:
                    for run in renderer["snippet"]["runs"]:
                        text = run.get("text", "").strip()
                        if text and text != "[Music]":
                            transcript_lines.append(text)
        return " ".join(transcript_lines) if transcript_lines else None
    except Exception as e:
        logger.error(f"Error parsing transcript segments: {e}")
        return None


def save_transcript_to_gcs(full_text: str, video_id: str) -> Optional[str]:
    """Save transcript text to GCS"""
    try:
        bucket = storage_client.bucket(TRANSCRIPTS_BUCKET_NAME)
        try:
            bucket.reload()
        except NotFound:
            bucket = storage_client.create_bucket(
                TRANSCRIPTS_BUCKET_NAME, location="us-central1"
            )
            logger.info(f"Created bucket: {TRANSCRIPTS_BUCKET_NAME}")

        blob_name = f"transcripts/{video_id}.txt"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(full_text, content_type="text/plain")
        logger.info(f"Saved transcript to GCS: {blob_name}")
        return f"gs://{TRANSCRIPTS_BUCKET_NAME}/{blob_name}"
    except Exception as e:
        logger.error(f"Error saving transcript to GCS: {e}")
        return None


def save_transcript_to_bigquery(video_id: str, full_text: str) -> bool:
    """Save transcript text to BigQuery"""
    try:
        dataset_ref = bigquery_client.dataset(DATASET_ID)
        table_ref = dataset_ref.table(TRANSCRIPTS_TABLE_ID)
        try:
            bigquery_client.get_table(table_ref)
        except NotFound:
            schema = [
                bigquery.SchemaField("video_id", "STRING", mode="REQUIRED"),
                bigquery.SchemaField("full_text", "STRING"),
                bigquery.SchemaField("processed_at", "TIMESTAMP"),
            ]
            table = bigquery.Table(table_ref, schema=schema)
            bigquery_client.create_table(table)
            logger.info(f"Created table: {TRANSCRIPTS_TABLE_ID}")

        row = {
            "video_id": video_id,
            "full_text": full_text,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        errors = bigquery_client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
            return False
        logger.info(f"Saved transcript to BigQuery: {video_id}")
        return True
    except Exception as e:
        logger.error(f"Error saving transcript to BigQuery: {e}")
        return False


def update_staging_table(video_id: str, transcript_file: str):
    """Update staging table with transcript info"""
    try:
        query = f"""
        MERGE `{PROJECT_ID}.{DATASET_ID}.{STAGING_TABLE_ID}` AS target
        USING (
            SELECT 
                '{video_id}' as video_id,
                TRUE as transcript_available,
                '{transcript_file}' as transcript_file,
                CURRENT_TIMESTAMP() as processed_at
        ) AS source
        ON target.video_id = source.video_id
        WHEN MATCHED THEN
            UPDATE SET 
                transcript_available = source.transcript_available,
                transcript_file = source.transcript_file,
                processed_at = source.processed_at
        WHEN NOT MATCHED THEN
            INSERT (video_id, transcript_available, transcript_file, processed_at)
            VALUES (
                source.video_id, 
                source.transcript_available, 
                source.transcript_file, 
                source.processed_at
            )
        """
        query_job = bigquery_client.query(query)
        query_job.result()
        logger.info(f"Updated staging table for video {video_id}")
        return True
    except Exception as e:
        logger.error(f"Error updating staging table: {e}")
        return False


@functions_framework.cloud_event
def get_transcripts_trigger(cloud_event):
    try:
        bucket_name = cloud_event.data["bucket"]
        file_name = cloud_event.data["name"]
        logger.info(f"Processing file: gs://{bucket_name}/{file_name}")

        if not file_name.startswith("videos/") or not file_name.endswith(".json"):
            logger.info(f"Skipping non-video file: {file_name}")
            return

        video_id = file_name.replace("videos/", "").replace(".json", "")
        transcript_bucket = storage_client.bucket(TRANSCRIPTS_BUCKET_NAME)
        transcript_blob = transcript_bucket.blob(f"transcripts/{video_id}.txt")

        if transcript_blob.exists():
            logger.info(f"Transcript already exists for video {video_id}")
            return {
                "status": "skipped",
                "video_id": video_id,
                "reason": "transcript_already_exists",
            }

        full_text = get_video_transcript_text(video_id)
        if not full_text:
            logger.warning(f"No transcript available for video {video_id}")
            return {"status": "no_transcript", "video_id": video_id}

        gcs_path = save_transcript_to_gcs(full_text, video_id)
        if gcs_path:
            save_transcript_to_bigquery(video_id, full_text)
            update_staging_table(video_id, gcs_path)

        return {"status": "success", "video_id": video_id, "gcs_path": gcs_path}

    except Exception as e:
        logger.error(f"Error in get_transcripts_trigger: {e}")
        return {"status": "error", "error": str(e)}
