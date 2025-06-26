import json
import os
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from flask import Flask, request, jsonify
from google.cloud import storage
from google.cloud.exceptions import NotFound
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
storage_client = storage.Client()

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'buoyant-yew-463209-k5')
SOURCE_BUCKET = os.environ.get('SOURCE_BUCKET', 'youtube-processed-data-bucket')
TRANSCRIPTS_BUCKET = os.environ.get('TRANSCRIPTS_BUCKET', 'youtube-processed-data-bucket')

# Oxylabs credentials
OXYLABS_USERNAME = os.environ.get('OXYLABS_USERNAME')
OXYLABS_PASSWORD = os.environ.get('OXYLABS_PASSWORD')

# Flask app
app = Flask(__name__)

def get_video_transcript_text(video_id: str) -> Optional[str]:
    """Fetch transcript for a YouTube video using Oxylabs"""
    try:
        if not OXYLABS_USERNAME or not OXYLABS_PASSWORD:
            logger.error("Oxylabs credentials not configured")
            return None

        payload = {
            'source': 'youtube_transcript',
            'query': video_id,
            'context': [
                {'key': 'language_code', 'value': 'en'},
                {'key': 'transcript_origin', 'value': 'auto_generated'}
            ]
        }

        response = requests.post(
            'https://realtime.oxylabs.io/v1/queries',
            auth=(OXYLABS_USERNAME, OXYLABS_PASSWORD),
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"Oxylabs request failed: {response.status_code}")
            return None

        data = response.json()
        if 'results' not in data or not data['results']:
            logger.error("No results from Oxylabs")
            return None

        result = data['results'][0]
        if 'content' in result and result['content']:
            transcript_text = parse_transcript_segments(result['content'])
            if transcript_text:
                logger.info(f"Successfully fetched transcript for video {video_id}")
                return transcript_text
            else:
                logger.warning(f"No transcript text extracted for video {video_id}")
                return None
        else:
            logger.warning(f"No transcript content found in Oxylabs response for video {video_id}")
            return None

    except Exception as e:
        logger.error(f"Error fetching transcript for video {video_id}: {e}")
        return None


def parse_transcript_segments(content: list) -> Optional[str]:
    """Parse transcript segments from Oxylabs response"""
    try:
        transcript_lines = []
        for segment in content:
            if 'transcriptSegmentRenderer' in segment:
                renderer = segment['transcriptSegmentRenderer']
                if 'snippet' in renderer and 'runs' in renderer['snippet']:
                    for run in renderer['snippet']['runs']:
                        text = run.get('text', '').strip()
                        if text and text != '[Music]':
                            transcript_lines.append(text)
        return ' '.join(transcript_lines) if transcript_lines else None
    except Exception as e:
        logger.error(f"Error parsing transcript segments: {e}")
        return None


def save_transcript_to_gcs(full_text: str, video_id: str) -> Optional[str]:
    """Save transcript text to GCS"""
    try:
        bucket = storage_client.bucket(TRANSCRIPTS_BUCKET)
        try:
            bucket.reload()
        except NotFound:
            bucket = storage_client.create_bucket(TRANSCRIPTS_BUCKET, location='us-central1')
            logger.info(f"Created bucket: {TRANSCRIPTS_BUCKET}")

        blob_name = f"transcripts/{video_id}.txt"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(full_text, content_type='text/plain')
        logger.info(f"Saved transcript to GCS: {blob_name}")
        return f"gs://{TRANSCRIPTS_BUCKET}/{blob_name}"
    except Exception as e:
        logger.error(f"Error saving transcript to GCS: {e}")
        return None


def update_video_metadata_with_transcript(video_id: str, transcript_file: str):
    """Update the video metadata file with transcript information"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        video_blob = bucket.blob(f"processed/videos/{video_id}.json")
        
        if not video_blob.exists():
            logger.warning(f"Video metadata file not found: {video_id}")
            return False
        
        # Download current video metadata
        video_content = video_blob.download_as_text()
        video_data = json.loads(video_content)
        
        # Update with transcript information
        video_data['transcript_available'] = True
        video_data['transcript_file'] = transcript_file
        video_data['transcript_processed_at'] = datetime.now(timezone.utc).isoformat()
        
        # Save updated metadata back to GCS
        video_blob.upload_from_string(
            json.dumps(video_data, indent=2), 
            content_type='application/json'
        )
        logger.info(f"Updated video metadata with transcript info: {video_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error updating video metadata: {e}")
        return False


def transcript_processor(cloud_event):
    """Process video files and fetch transcripts"""
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
        
        # Only process video files in the processed/videos/ folder
        if not file_name.startswith('processed/videos/') or not file_name.endswith('.json'):
            logger.info(f"Skipping non-video file: {file_name}")
            return f"Skipped non-video file: {file_name}"
        
        # Extract video ID from filename
        video_id = file_name.replace('processed/videos/', '').replace('.json', '')
        logger.info(f"Processing transcript for video: {video_id}")
        
        # Check if transcript already exists
        transcript_bucket = storage_client.bucket(TRANSCRIPTS_BUCKET)
        transcript_blob = transcript_bucket.blob(f"transcripts/{video_id}.txt")
        
        if transcript_blob.exists():
            logger.info(f"Transcript already exists for video {video_id}")
            return {
                'status': 'skipped',
                'video_id': video_id,
                'reason': 'transcript_already_exists'
            }
        
        # Fetch transcript from Oxylabs
        full_text = get_video_transcript_text(video_id)
        if not full_text:
            logger.warning(f"No transcript available for video {video_id}")
            return {
                'status': 'no_transcript',
                'video_id': video_id
            }
        
        # Save transcript to GCS
        gcs_path = save_transcript_to_gcs(full_text, video_id)
        if gcs_path:
            # Update video metadata with transcript information
            update_video_metadata_with_transcript(video_id, gcs_path)
            
            logger.info(f"Successfully processed transcript for video {video_id}")
            return {
                'status': 'success',
                'video_id': video_id,
                'gcs_path': gcs_path,
                'transcript_length': len(full_text)
            }
        else:
            logger.error(f"Failed to save transcript for video {video_id}")
            return {
                'status': 'error',
                'video_id': video_id,
                'error': 'Failed to save transcript'
            }

    except Exception as e:
        logger.error(f"Error in transcript_processor: {e}")
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
    return jsonify({"status": "healthy", "service": "youtube-transcript-processor"})


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
        result = transcript_processor(cloud_event)
        return jsonify({"result": result}), 200
        
    except Exception as e:
        logger.error(f"Error in process_webhook: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False) 