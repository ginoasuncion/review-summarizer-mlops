import json
import os
import logging
import openai
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
SUMMARIES_BUCKET = os.environ.get('SUMMARIES_BUCKET', 'youtube-processed-data-bucket')

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

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

def generate_summary_with_chatgpt(transcript: str, video_metadata: Dict[str, Any]) -> Optional[str]:
    """Generate summary using ChatGPT"""
    try:
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not configured")
            return None
        
        # Set up OpenAI client
        openai.api_key = OPENAI_API_KEY
        
        # Create prompt for summarization
        title = video_metadata.get('title', 'Unknown Title')
        channel = video_metadata.get('channel_name', 'Unknown Channel')
        search_query = video_metadata.get('search_query', 'Unknown Query')
        
        prompt = f"""
Please provide a comprehensive summary of this YouTube video transcript. 

Video Details:
- Title: {title}
- Channel: {channel}
- Search Query: {search_query}

Transcript:
{transcript}

Please provide a structured summary that includes:
1. **Main Topic**: What is the video about?
2. **Key Points**: What are the main points discussed?
3. **Product Review Details** (if applicable): What products are reviewed and what are the findings?
4. **Recommendations**: What recommendations or conclusions are made?
5. **Overall Rating/Opinion**: What is the overall sentiment or rating?

Format the summary in a clear, structured manner with bullet points where appropriate.
Keep the summary concise but comprehensive (around 200-300 words).
"""

        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes YouTube video transcripts, especially product reviews and comparisons."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content.strip()
        logger.info(f"Generated summary for video {video_metadata.get('video_id', 'unknown')} ({len(summary)} characters)")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating summary with ChatGPT: {e}")
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
        
        # Generate summary with ChatGPT
        summary = generate_summary_with_chatgpt(transcript_content, video_metadata)
        if not summary:
            logger.warning(f"Failed to generate summary for video {video_id}")
            return {
                'status': 'summary_generation_failed',
                'video_id': video_id
            }
        
        # Save summary to GCS
        gcs_path = save_summary_to_gcs(summary, video_id)
        if gcs_path:
            # Update video metadata with summary information
            update_video_metadata_with_summary(video_id, gcs_path)
            
            logger.info(f"Successfully processed summary for video {video_id}")
            return {
                'status': 'success',
                'video_id': video_id,
                'gcs_path': gcs_path,
                'summary_length': len(summary)
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