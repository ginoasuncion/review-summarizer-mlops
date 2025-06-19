import json
import logging
import os
from datetime import datetime
from typing import Any, Dict

import functions_framework
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GCP Clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

# Environment Variables
PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
BUCKET_NAME = os.environ.get("GCP_BUCKET_NAME", "youtube-data-pipeline")
DATASET_ID = "youtube_data"
STAGING_TABLE_ID = "staging_video_metadata"
PARSED_BUCKET_NAME = f"{BUCKET_NAME}-parsed"


@functions_framework.cloud_event
def parse_videos_trigger(cloud_event):
    try:
        bucket_name = cloud_event.data["bucket"]
        file_name = cloud_event.data["name"]

        if not file_name.startswith("raw_data/") or not file_name.endswith(".json"):
            logger.info(f"Skipping non-raw file: {file_name}")
            return

        logger.info(f"Processing file: gs://{bucket_name}/{file_name}")

        # Load JSON from GCS
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        raw_content = blob.download_as_text()
        raw_data = json.loads(raw_content)
        raw_data["source_file"] = file_name

        if "results" not in raw_data or not raw_data["results"]:
            logger.error("No results found")
            return

        first_result = raw_data["results"][0]
        if "content" not in first_result:
            logger.error("No content found")
            return

        for video in first_result["content"]:
            video_data = parse_video_data(video, raw_data)
            if not video_data:
                continue

            video_id = video_data.get("video_id")
            if not video_id:
                logger.warning("Missing video_id")
                continue

            save_to_gcs(video_data, video_id)
            save_to_bigquery(video_data)

    except Exception as e:
        logger.error(f"Failed to process event: {e}")


def parse_video_data(video: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
    try:

        def get_text(obj):
            if isinstance(obj, dict):
                if "simpleText" in obj:
                    return obj["simpleText"]
                if "runs" in obj:
                    return " ".join(run.get("text", "") for run in obj["runs"])
            return ""

        def get_channel_id(obj):
            try:
                return obj["runs"][0]["navigationEndpoint"]["browseEndpoint"][
                    "browseId"
                ]
            except (KeyError, IndexError):
                return ""

        def get_description(obj):
            if "runs" in obj:
                return " ".join(run.get("text", "") for run in obj["runs"])
            return ""

        video_info = {
            "video_id": video.get("videoId", ""),
            "title": get_text(video.get("title", {})),
            "channel_name": get_text(video.get("longBylineText", {})),
            "channel_id": get_channel_id(video.get("longBylineText", {})),
            "published_date": get_text(video.get("publishedTimeText", {})),
            "duration": get_text(video.get("lengthText", {})),
            "views": get_text(video.get("viewCountText", {})),
            "thumbnail_url": video.get("thumbnail", {})
            .get("thumbnails", [{}])[0]
            .get("url", ""),
            "watch_url": f"https://www.youtube.com/watch?v={video.get('videoId', '')}",
            "description": get_description(video.get("descriptionSnippet", {})),
            "category": "",
            "language": "en",
            "processed_at": datetime.utcnow().isoformat(),
            "raw_data_file": raw_data.get("source_file", ""),
            "search_query": raw_data.get("search_query", ""),
            "transcript_available": False,
            "transcript_file": None,
        }

        # Convert views
        try:
            views = video_info["views"].replace(",", "").replace(" views", "")
            if "K" in views:
                views = float(views.replace("K", "")) * 1_000
            elif "M" in views:
                views = float(views.replace("M", "")) * 1_000_000
            video_info["views"] = int(views)
        except (ValueError, AttributeError):
            video_info["views"] = 0

        # Convert duration
        try:
            parts = video_info["duration"].split(":")
            if len(parts) == 2:
                video_info["duration_seconds"] = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                video_info["duration_seconds"] = (
                    int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                )
            else:
                video_info["duration_seconds"] = 0
        except (ValueError, AttributeError):
            video_info["duration_seconds"] = 0

        return video_info

    except Exception as e:
        logger.error(f"Failed to parse video data: {e}")
        return None


def save_to_gcs(video_data: Dict[str, Any], video_id: str):
    try:
        bucket = storage_client.bucket(PARSED_BUCKET_NAME)
        try:
            bucket.reload()
        except NotFound:
            storage_client.create_bucket(PARSED_BUCKET_NAME, location="us-central1")
            logger.info(f"Created bucket: {PARSED_BUCKET_NAME}")
        blob = bucket.blob(f"videos/{video_id}.json")
        blob.upload_from_string(json.dumps(video_data), content_type="application/json")
        logger.info(f"Saved video to GCS: {video_id}")
    except Exception as e:
        logger.error(f"GCS save error: {e}")


def save_to_bigquery(video_data: Dict[str, Any]) -> bool:
    try:
        dataset_ref = bigquery_client.dataset(DATASET_ID)
        table_ref = dataset_ref.table(STAGING_TABLE_ID)
        bigquery_client.get_table(table_ref)

        default_fields = {
            "video_id": "",
            "title": "",
            "channel_name": "",
            "channel_id": "",
            "published_date": "",
            "duration": "",
            "duration_seconds": 0,
            "views": 0,
            "thumbnail_url": "",
            "watch_url": "",
            "description": "",
            "category": "",
            "language": "en",
            "processed_at": datetime.utcnow().isoformat(),
            "raw_data_file": "",
            "search_query": "",
            "transcript_available": False,
            "transcript_file": None,
        }

        for key, default in default_fields.items():
            video_data.setdefault(key, default)

        errors = bigquery_client.insert_rows_json(table_ref, [video_data])
        if errors:
            logger.error(f"BigQuery insert failed: {errors}")
            return False

        logger.info(f"Inserted video into BigQuery: {video_data['video_id']}")
        return True

    except Exception as e:
        logger.error(f"BigQuery insert error: {e}")
        return False
