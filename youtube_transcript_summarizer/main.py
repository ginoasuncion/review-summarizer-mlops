import json
import os
import logging
import openai
import time
import random
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify
from google.cloud import storage
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import base64
import requests
import functions_framework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'buoyant-yew-463209-k5')
SOURCE_BUCKET = os.environ.get('SOURCE_BUCKET', 'youtube-processed-data-bucket')
SUMMARIES_BUCKET = os.environ.get('SUMMARIES_BUCKET', 'youtube-processed-data-bucket')

# BigQuery Configuration
BIGQUERY_DATASET = os.environ.get('BIGQUERY_DATASET', 'youtube_reviews')
BIGQUERY_PROJECT = os.environ.get('BIGQUERY_PROJECT', PROJECT_ID)
VIDEO_METADATA_TABLE = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.video_metadata"

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o')

# LLM Judge Configuration
LLM_JUDGE_PROBABILITY = float(os.environ.get('LLM_JUDGE_PROBABILITY', '0.2'))  # 20% chance by default
LLM_JUDGE_API_URL = "https://llm-judge-api-nxbmt7mfiq-uc.a.run.app/evaluate"

# Flask app
app = Flask(__name__)

def get_transcript_content(video_id: str) -> Optional[str]:
    """Get transcript content from GCS"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        transcript_blob = bucket.blob(f"transcripts/{video_id}.txt")
        
        if not transcript_blob.exists():
            logger.warning(f"Transcript file not found: {video_id}")
            return None
        
        content = transcript_blob.download_as_text()
        logger.info(f"Retrieved transcript for video {video_id} ({len(content)} characters)")
        return content
        
    except Exception as e:
        logger.error(f"Error retrieving transcript for video {video_id}: {e}")
        return None

def get_video_metadata(video_id: str) -> Optional[Dict[str, Any]]:
    """Get video metadata from GCS"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        video_blob = bucket.blob(f"processed/videos/{video_id}.json")
        
        if not video_blob.exists():
            logger.warning(f"Video metadata file not found: {video_id}")
            return None
        
        content = video_blob.download_as_text()
        metadata = json.loads(content)
        logger.info(f"Retrieved metadata for video {video_id}")
        return metadata
        
    except Exception as e:
        logger.error(f"Error retrieving metadata for video {video_id}: {e}")
        return None

def generate_summary_with_llm_judge(transcript: str, video_metadata: Dict[str, Any], max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Generate summary using OpenAI and optionally evaluate with LLM Judge API"""
    for attempt in range(max_retries + 1):
        try:
            if not OPENAI_API_KEY:
                logger.error("OpenAI API key not configured")
                return None
            
            # Set up OpenAI client
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Extract product name from search query or title
            search_query = video_metadata.get('search_query', 'Unknown Query')
            title = video_metadata.get('title', 'Unknown Title')
            
            # Try to extract product name from search query or title
            product = search_query
            if 'review' in search_query.lower():
                product = search_query.replace('review', '').strip()
            elif 'review' in title.lower():
                product = title.replace('review', '').strip()
            
            # Create the new focused prompt for shoe reviews
            prompt = f"""You are a helpful, enthusiastic product reviewer assistant.

Summarize the following transcript of a review for the shoe model: {product}.
Your goal is to create a clear, engaging, and friendly summary that feels like a recommendation from a trusted friend.

Emphasize:
- What the reviewer liked or disliked
- Comfort (daily wear, cushioning, sizing)
- Fit (true to size? narrow? wide?)
- Durability (build quality, longevity, visible wear)
- Performance (how it feels while walking/running, use cases)
- Style (appearance, versatility, colorways)

Avoid repeating the transcript. Keep it grounded in what was actually said.

Transcript:
{transcript}"""

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful, enthusiastic product reviewer assistant that creates engaging, friendly summaries of shoe reviews."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated summary for video {video_metadata.get('video_id', 'unknown')} ({len(summary)} characters)")
            
            # Only evaluate with LLM judge for randomly selected videos
            llm_scores = None
            video_id = video_metadata.get('video_id', 'unknown')
            
            if should_evaluate_with_llm_judge(search_query, video_id):
                # Evaluate the summary with LLM judge
                llm_scores = call_llm_judge_api(summary, search_query, title)
            else:
                logger.info(f"Skipping LLM judge evaluation for video {video_id}")
            
            return {
                'summary': summary,
                'llm_scores': llm_scores
            }
            
        except openai.RateLimitError as e:
            if attempt < max_retries:
                # Calculate backoff time (exponential backoff with jitter)
                backoff_time = min(2 ** attempt + (time.time() % 1), 60)  # Cap at 60 seconds
                logger.warning(f"Rate limit hit during summary generation, retrying in {backoff_time:.1f} seconds (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(backoff_time)
                continue
            else:
                logger.error(f"Rate limit exceeded after {max_retries + 1} attempts during summary generation: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating summary with OpenAI: {e}")
            return None
    
    return None

def save_summary_to_gcs(summary: str, video_id: str) -> Optional[str]:
    """Save summary to GCS"""
    try:
        bucket = storage_client.bucket(SUMMARIES_BUCKET)
        try:
            bucket.reload()
        except NotFound:
            bucket = storage_client.create_bucket(SUMMARIES_BUCKET, location='us-central1')
            logger.info(f"Created bucket: {SUMMARIES_BUCKET}")

        blob_name = f"summaries/{video_id}.txt"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(summary, content_type='text/plain')
        logger.info(f"Saved summary to GCS: {blob_name}")
        return f"gs://{SUMMARIES_BUCKET}/{blob_name}"
    except Exception as e:
        logger.error(f"Error saving summary to GCS: {e}")
        return None

def update_video_metadata_with_summary(video_id: str, summary_file: str):
    """Update the video metadata file with summary information"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        video_blob = bucket.blob(f"processed/videos/{video_id}.json")
        
        if not video_blob.exists():
            logger.warning(f"Video metadata file not found: {video_id}")
            return False
        
        # Download current video metadata
        video_content = video_blob.download_as_text()
        video_data = json.loads(video_content)
        
        # Update with summary information
        video_data['summary_available'] = True
        video_data['summary_file'] = summary_file
        video_data['summary_processed_at'] = datetime.now(timezone.utc).isoformat()
        
        # Save updated metadata back to GCS
        video_blob.upload_from_string(
            json.dumps(video_data, indent=2), 
            content_type='application/json'
        )
        logger.info(f"Updated video metadata with summary info: {video_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating video metadata: {e}")
        return False

def update_video_metadata_in_bigquery(video_metadata: Dict[str, Any], summary_file: str, summary_content: str, llm_scores: Optional[Dict[str, float]] = None):
    """Update video metadata in BigQuery with summary information"""
    try:
        video_id = video_metadata.get('video_id', '')
        
        # Prepare the row data for BigQuery
        row = {
            'video_id': video_id,
            'title': video_metadata.get('title', ''),
            'channel_title': video_metadata.get('channel_title', ''),
            'description': video_metadata.get('description', ''),
            'published_at': video_metadata.get('published_at'),
            'view_count': video_metadata.get('view_count', 0),
            'like_count': video_metadata.get('like_count', 0),
            'comment_count': video_metadata.get('comment_count', 0),
            'duration': video_metadata.get('duration', ''),
            'tags': video_metadata.get('tags', []),
            'category_id': video_metadata.get('category_id', ''),
            'default_language': video_metadata.get('default_language', ''),
            'default_audio_language': video_metadata.get('default_audio_language', ''),
            'search_query': video_metadata.get('search_query', ''),
            'summary_available': True,
            'summary_content': summary_content,
            'processed_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Add LLM judge scores if available
        if llm_scores:
            row['llm_relevance_score'] = llm_scores.get('relevance')
            row['llm_helpfulness_score'] = llm_scores.get('helpfulness')
            row['llm_conciseness_score'] = llm_scores.get('conciseness')
        
        # Use parameterized query to safely handle text content
        merge_query = f"""
        MERGE `{VIDEO_METADATA_TABLE}` AS target
        USING (SELECT @video_id as video_id) AS source
        ON target.video_id = source.video_id
        WHEN MATCHED THEN
            UPDATE SET
                title = @title,
                channel_title = @channel_title,
                description = @description,
                published_at = @published_at,
                view_count = @view_count,
                like_count = @like_count,
                comment_count = @comment_count,
                duration = @duration,
                category_id = @category_id,
                default_language = @default_language,
                default_audio_language = @default_audio_language,
                search_query = @search_query,
                summary_available = @summary_available,
                summary_content = @summary_content,
                processed_at = @processed_at,
                llm_relevance_score = @llm_relevance_score,
                llm_helpfulness_score = @llm_helpfulness_score,
                llm_conciseness_score = @llm_conciseness_score
        WHEN NOT MATCHED THEN
            INSERT (video_id, title, channel_title, description, published_at, view_count, like_count, comment_count, duration, category_id, default_language, default_audio_language, search_query, summary_available, summary_content, processed_at, llm_relevance_score, llm_helpfulness_score, llm_conciseness_score)
            VALUES (@video_id, @title, @channel_title, @description, @published_at, @view_count, @like_count, @comment_count, @duration, @category_id, @default_language, @default_audio_language, @search_query, @summary_available, @summary_content, @processed_at, @llm_relevance_score, @llm_helpfulness_score, @llm_conciseness_score)
        """
        
        # Create query parameters
        query_parameters = [
            bigquery.ScalarQueryParameter("video_id", "STRING", row['video_id']),
            bigquery.ScalarQueryParameter("title", "STRING", row['title']),
            bigquery.ScalarQueryParameter("channel_title", "STRING", row['channel_title']),
            bigquery.ScalarQueryParameter("description", "STRING", row['description']),
            bigquery.ScalarQueryParameter("published_at", "TIMESTAMP", row['published_at'] if row['published_at'] not in [None, '', 'None'] else None),
            bigquery.ScalarQueryParameter("view_count", "INTEGER", row['view_count']),
            bigquery.ScalarQueryParameter("like_count", "INTEGER", row['like_count']),
            bigquery.ScalarQueryParameter("comment_count", "INTEGER", row['comment_count']),
            bigquery.ScalarQueryParameter("duration", "STRING", row['duration']),
            bigquery.ScalarQueryParameter("category_id", "STRING", row['category_id']),
            bigquery.ScalarQueryParameter("default_language", "STRING", row['default_language']),
            bigquery.ScalarQueryParameter("default_audio_language", "STRING", row['default_audio_language']),
            bigquery.ScalarQueryParameter("search_query", "STRING", row['search_query']),
            bigquery.ScalarQueryParameter("summary_available", "BOOL", row['summary_available']),
            bigquery.ScalarQueryParameter("summary_content", "STRING", row['summary_content']),
            bigquery.ScalarQueryParameter("processed_at", "TIMESTAMP", row['processed_at']),
            bigquery.ScalarQueryParameter("llm_relevance_score", "FLOAT", row.get('llm_relevance_score')),
            bigquery.ScalarQueryParameter("llm_helpfulness_score", "FLOAT", row.get('llm_helpfulness_score')),
            bigquery.ScalarQueryParameter("llm_conciseness_score", "FLOAT", row.get('llm_conciseness_score'))
        ]
        
        # Execute the parameterized query
        job_config = bigquery.QueryJobConfig(query_parameters=query_parameters)
        query_job = bigquery_client.query(merge_query, job_config=job_config)
        query_job.result()  # Wait for the query to complete
        
        logger.info(f"Successfully updated video metadata in BigQuery: {video_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating video metadata in BigQuery: {e}")
        return False

def should_evaluate_with_llm_judge(search_query: str, video_id: str) -> bool:
    """
    Determine if this video should be evaluated by the LLM judge.
    Uses a deterministic random selection based on search query to ensure
    only one video per search query gets evaluated.
    """
    # Use search query as seed for deterministic randomness
    random.seed(hash(search_query) % (2**32))
    
    # Generate a random number between 0 and 1
    random_value = random.random()
    
    # Reset seed to avoid affecting other random operations
    random.seed()
    
    should_evaluate = random_value < LLM_JUDGE_PROBABILITY
    
    if should_evaluate:
        logger.info(f"Selected video {video_id} for LLM judge evaluation (query: {search_query})")
    else:
        logger.info(f"Skipping LLM judge evaluation for video {video_id} (query: {search_query})")
    
    return should_evaluate

def call_llm_judge_api(summary_content: str, search_query: str, video_title: str = None) -> Optional[Dict[str, float]]:
    """
    Call the LLM Judge API to evaluate a summary.
    """
    try:
        payload = {
            "summary_content": summary_content,
            "search_query": search_query,
            "video_title": video_title,
            "openai_model": "gpt-4o",
            "max_retries": 3
        }
        
        response = requests.post(LLM_JUDGE_API_URL, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        if result.get("success") and result.get("scores"):
            logger.info(f"LLM Judge API scores: {result['scores']}")
            return result["scores"]
        else:
            logger.error(f"LLM Judge API failed: {result.get('error', 'Unknown error')}")
            return None
            
    except Exception as e:
        logger.error(f"Error calling LLM Judge API: {e}")
        return None

def transcript_summarizer(cloud_event):
    """Process transcript files and generate summaries"""
    try:
        # Extract event data
        event_data = cloud_event.data
        
        bucket_name = event_data.get('bucket')
        file_name = event_data.get('name')
        event_type = event_data.get('eventType')
        
        # For Pub/Sub messages, eventType might be in attributes
        if not event_type and 'attributes' in event_data:
            event_type = event_data['attributes'].get('eventType')
        
        logger.info(f"Processing event: {event_type} for file: gs://{bucket_name}/{file_name}")
        
        # Only process new file uploads
        if event_type != 'OBJECT_FINALIZE':
            logger.info(f"Skipping event type: {event_type}")
            return f"Skipped event type: {event_type}"
        
        # Only process files from the source bucket
        if bucket_name != SOURCE_BUCKET:
            logger.info(f"Skipping file from bucket: {bucket_name}")
            return f"Skipped file from bucket: {bucket_name}"
        
        # Only process transcript files in the transcripts/ folder
        if not file_name.startswith('transcripts/') or not file_name.endswith('.txt'):
            logger.info(f"Skipping non-transcript file: {file_name}")
            return f"Skipped non-transcript file: {file_name}"
        
        # Extract video ID from filename
        video_id = file_name.replace('transcripts/', '').replace('.txt', '')
        logger.info(f"Processing summary for video: {video_id}")
        
        # Check if summary already exists
        summary_bucket = storage_client.bucket(SUMMARIES_BUCKET)
        summary_blob = summary_bucket.blob(f"summaries/{video_id}.txt")
        
        if summary_blob.exists():
            logger.info(f"Summary already exists for video {video_id}")
            return {
                'status': 'skipped',
                'video_id': video_id,
                'reason': 'summary_already_exists'
            }
        
        # Get transcript content
        transcript_content = get_transcript_content(video_id)
        if not transcript_content:
            logger.warning(f"No transcript content available for video {video_id}")
            return {
                'status': 'no_transcript',
                'video_id': video_id
            }
        
        # Get video metadata
        video_metadata = get_video_metadata(video_id)
        if not video_metadata:
            logger.warning(f"No video metadata available for video {video_id}")
            return {
                'status': 'no_metadata',
                'video_id': video_id
            }
        
        # Generate summary with LLM Judge
        summary_data = generate_summary_with_llm_judge(transcript_content, video_metadata)
        if not summary_data:
            logger.warning(f"Failed to generate summary for video {video_id}")
            return {
                'status': 'summary_generation_failed',
                'video_id': video_id
            }
        
        # Save summary to GCS
        gcs_path = save_summary_to_gcs(summary_data['summary'], video_id)
        if gcs_path:
            # Update video metadata with summary information
            update_video_metadata_with_summary(video_id, gcs_path)
            
            # Update video metadata in BigQuery
            update_video_metadata_in_bigquery(video_metadata, gcs_path, summary_data['summary'], summary_data['llm_scores'])
            
            logger.info(f"Successfully processed summary for video {video_id}")
            return {
                'status': 'success',
                'video_id': video_id,
                'gcs_path': gcs_path,
                'summary_length': len(summary_data['summary']),
                'llm_scores': summary_data['llm_scores']
            }
        else:
            logger.error(f"Failed to save summary for video {video_id}")
            return {
                'status': 'error',
                'video_id': video_id,
                'error': 'Failed to save summary'
            }

    except Exception as e:
        logger.error(f"Error in transcript_summarizer: {e}")
        return {'status': 'error', 'error': str(e)}


# CloudEvent class for compatibility
class CloudEvent:
    def __init__(self, type, source, data):
        self.type = type
        self.source = source
        self.data = data


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "youtube-transcript-summarizer"})


@app.route('/process', methods=['POST'])
def process_webhook():
    """Process Cloud Storage event via HTTP webhook"""
    try:
        # Get the event data from the request
        event_data = request.get_json()
        
        if not event_data:
            return jsonify({"error": "No event data provided"}), 400
        
        # Debug logging
        logger.info(f"Received webhook data: {json.dumps(event_data, indent=2)}")
        
        # Handle Pub/Sub message format from Cloud Storage notifications
        if 'message' in event_data:
            # This is a Pub/Sub message format
            import json as json_lib
            
            # Decode the Pub/Sub message
            message_data = event_data['message']
            logger.info(f"Pub/Sub message data: {json.dumps(message_data, indent=2)}")
            
            if 'data' in message_data:
                # Decode base64 data
                decoded_data = base64.b64decode(message_data['data']).decode('utf-8')
                logger.info(f"Decoded data: {decoded_data}")
                storage_event = json_lib.loads(decoded_data)
                logger.info(f"Storage event: {json.dumps(storage_event, indent=2)}")
                
                # Extract eventType from Pub/Sub message attributes
                event_type = None
                if 'attributes' in message_data:
                    event_type = message_data['attributes'].get('eventType')
                    logger.info(f"Event type from attributes: {event_type}")
                
                # Add eventType to storage event if not present
                if event_type and 'eventType' not in storage_event:
                    storage_event['eventType'] = event_type
                
                # Create a CloudEvent-like object
                cloud_event = CloudEvent(
                    type="google.cloud.storage.object.v1.finalized",
                    source="//storage.googleapis.com/projects/_/buckets/youtube-processed-data-bucket",
                    data=storage_event
                )
            else:
                return jsonify({"error": "Invalid Pub/Sub message format"}), 400
        else:
            # This is a direct HTTP request format
            logger.info("Direct HTTP request format")
            cloud_event = CloudEvent(
                type="google.cloud.storage.object.v1.finalized",
                source="//storage.googleapis.com/projects/_/buckets/youtube-processed-data-bucket",
                data=event_data
            )
        
        # Process the event
        result = transcript_summarizer(cloud_event)
        return jsonify({"result": result}), 200
        
    except Exception as e:
        logger.error(f"Error in process_webhook: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False) 