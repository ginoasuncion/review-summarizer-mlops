"""
YouTube Data Processor Cloud Function

This function is triggered by Cloud Storage events when new YouTube search data
is uploaded to the source bucket. It processes the raw search data and extracts
key information for each video, then saves the processed data to a destination bucket.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Any

from google.cloud import storage
from google.cloud.exceptions import NotFound
import base64

# Try to import Cloud Function dependencies (only needed for deployment)
try:
    from google.cloud import functions_v1
    from google.cloud.functions_v1 import CloudEvent
    CLOUD_FUNCTION_AVAILABLE = True
except ImportError:
    CLOUD_FUNCTION_AVAILABLE = False
    # Mock CloudEvent for local testing
    class CloudEvent:
        def __init__(self, type, source, data):
            self.type = type
            self.source = source
            self.data = data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
SOURCE_BUCKET = os.getenv('SOURCE_BUCKET', 'youtube-search-data-bucket')
DEST_BUCKET = os.getenv('DESTINATION_BUCKET', 'youtube-processed-data-bucket')
PROJECT_ID = os.getenv('GOOGLE_CLOUD_PROJECT')

# Initialize GCS client (only when needed)
storage_client = None

def get_storage_client():
    """Get or create the storage client"""
    global storage_client
    if storage_client is None:
        storage_client = storage.Client()
    return storage_client


def extract_video_info(video_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract key information from a video search result.
    
    Args:
        video_data: Raw video data from YouTube search
        
    Returns:
        Dict containing processed video information
    """
    try:
        # Extract basic video information
        video_info = {
            'video_id': video_data.get('id', {}).get('videoId', ''),
            'title': video_data.get('snippet', {}).get('title', ''),
            'description': video_data.get('snippet', {}).get('description', ''),
            'channel_title': video_data.get('snippet', {}).get('channelTitle', ''),
            'channel_id': video_data.get('snippet', {}).get('channelId', ''),
            'published_at': video_data.get('snippet', {}).get('publishedAt', ''),
            'thumbnails': video_data.get('snippet', {}).get('thumbnails', {}),
            'tags': video_data.get('snippet', {}).get('tags', []),
            'category_id': video_data.get('snippet', {}).get('categoryId', ''),
            'default_language': video_data.get('snippet', {}).get('defaultLanguage', ''),
            'default_audio_language': video_data.get('snippet', {}).get('defaultAudioLanguage', ''),
        }
        
        # Extract statistics if available
        if 'statistics' in video_data:
            stats = video_data['statistics']
            video_info.update({
                'view_count': int(stats.get('viewCount', 0)),
                'like_count': int(stats.get('likeCount', 0)),
                'comment_count': int(stats.get('commentCount', 0)),
                'favorite_count': int(stats.get('favoriteCount', 0)),
            })
        
        # Extract content details if available
        if 'contentDetails' in video_data:
            content = video_data['contentDetails']
            video_info.update({
                'duration': content.get('duration', ''),
                'dimension': content.get('dimension', ''),
                'definition': content.get('definition', ''),
                'caption': content.get('caption', ''),
                'licensed_content': content.get('licensedContent', False),
                'projection': content.get('projection', ''),
            })
        
        # Extract status if available
        if 'status' in video_data:
            status = video_data['status']
            video_info.update({
                'upload_status': status.get('uploadStatus', ''),
                'privacy_status': status.get('privacyStatus', ''),
                'license': status.get('license', ''),
                'embeddable': status.get('embeddable', False),
                'public_stats_viewable': status.get('publicStatsViewable', False),
                'made_for_kids': status.get('madeForKids', False),
            })
        
        return video_info
        
    except Exception as e:
        logger.error(f"Error extracting video info: {e}")
        return {}


def process_search_data(raw_data: Dict[str, Any], file_name: str) -> Dict[str, Any]:
    """
    Process raw YouTube search data and extract key information.
    
    Args:
        raw_data: Raw search data from Oxylabs API
        file_name: Source file name containing search query
        
    Returns:
        Dict containing processed search results
    """
    try:
        # Extract search query from filename or job data
        search_query = extract_search_query_from_filename(file_name)
        
        # If we have job data with query, use that instead
        if 'job' in raw_data and 'query' in raw_data['job']:
            search_query = raw_data['job']['query']
        
        # Extract search metadata
        search_info = {
            'search_query': search_query,
            'search_timestamp': raw_data.get('job', {}).get('created_at', ''),
            'total_results': len(raw_data.get('results', [])),
            'results_per_page': len(raw_data.get('results', [])),
            'next_page_token': '',
            'region_code': '',
            'source_file': file_name,
            'job_id': raw_data.get('job', {}).get('id', ''),
            'job_status': raw_data.get('job', {}).get('status', ''),
        }
        
        # Process each video in the search results (Oxylabs format)
        videos = []
        results = raw_data.get('results', [])
        
        for result in results:
            content = result.get('content', [])
            for video_data in content:
                video_info = extract_oxylabs_video_info(video_data)
                if video_info:
                    videos.append(video_info)
        
        # Create processed data structure
        processed_data = {
            'search_info': search_info,
            'videos': videos,
            'video_count': len(videos),
            'processing_timestamp': datetime.utcnow().isoformat(),
            'processing_version': '1.0.0'
        }
        
        return processed_data
        
    except Exception as e:
        logger.error(f"Error processing search data: {e}")
        return {}


def extract_search_query_from_filename(file_name: str) -> str:
    """
    Extract search query from the filename.
    
    Expected filename format: raw_data/youtube_search_search_query_YYYYMMDD_HHMMSS.json
    or: youtube_search_search_query_YYYYMMDD_HHMMSS.json
    
    Args:
        file_name: The filename to parse
        
    Returns:
        The search query extracted from the filename
    """
    try:
        # Remove the raw_data/ prefix if present
        if file_name.startswith('raw_data/'):
            file_name = file_name[9:]  # Remove 'raw_data/' prefix
        
        # Remove .json extension
        base_name = os.path.splitext(file_name)[0]
        
        # Remove 'youtube_search_' prefix if present
        if base_name.startswith('youtube_search_'):
            base_name = base_name[15:]  # Remove 'youtube_search_' prefix
        
        # Split by underscore and find the timestamp pattern
        parts = base_name.split('_')
        
        # Look for timestamp pattern (YYYYMMDD_HHMMSS)
        timestamp_pattern = None
        for i, part in enumerate(parts):
            if len(part) == 8 and part.isdigit():  # YYYYMMDD
                if i + 1 < len(parts) and len(parts[i + 1]) == 6 and parts[i + 1].isdigit():  # HHMMSS
                    timestamp_pattern = i
                    break
        
        if timestamp_pattern is not None:
            # Everything before the timestamp is the search query
            search_query_parts = parts[:timestamp_pattern]
            search_query = ' '.join(search_query_parts)
        else:
            # Fallback: remove the last part if it looks like a timestamp
            if len(parts) > 1 and parts[-1].isdigit() and len(parts[-1]) >= 6:
                search_query_parts = parts[:-1]
                search_query = ' '.join(search_query_parts)
            else:
                # If no clear pattern, use the whole filename
                search_query = base_name
        
        # Clean up the search query
        search_query = search_query.replace('_', ' ').strip()
        
        logger.info(f"Extracted search query '{search_query}' from filename '{file_name}'")
        return search_query
        
    except Exception as e:
        logger.error(f"Error extracting search query from filename '{file_name}': {e}")
        return "unknown_query"


def extract_oxylabs_video_info(video_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract key information from a video in Oxylabs format.
    
    Args:
        video_data: Raw video data from Oxylabs API
        
    Returns:
        Dict containing processed video information
    """
    try:
        # Extract title text from the title object
        title_text = ""
        if 'title' in video_data and 'runs' in video_data['title']:
            title_runs = video_data['title']['runs']
            if title_runs and 'text' in title_runs[0]:
                title_text = title_runs[0]['text']
        
        # Extract channel info from byline text
        channel_title = ""
        if 'shortBylineText' in video_data and 'runs' in video_data['shortBylineText']:
            byline_runs = video_data['shortBylineText']['runs']
            if byline_runs and 'text' in byline_runs[0]:
                channel_title = byline_runs[0]['text']
        
        # Extract view count
        view_count = 0
        if 'viewCountText' in video_data and 'runs' in video_data['viewCountText']:
            view_runs = video_data['viewCountText']['runs']
            if view_runs and 'text' in view_runs[0]:
                view_text = view_runs[0]['text']
                # Extract numbers from view count text (e.g., "1.2M views" -> 1200000)
                import re
                numbers = re.findall(r'[\d,]+', view_text.replace(',', ''))
                if numbers:
                    view_count = int(numbers[0])
        
        # Extract duration
        duration = ""
        if 'lengthText' in video_data and 'runs' in video_data['lengthText']:
            length_runs = video_data['lengthText']['runs']
            if length_runs and 'text' in length_runs[0]:
                duration = length_runs[0]['text']
        
        # Extract published time
        published_at = ""
        if 'publishedTimeText' in video_data and 'runs' in video_data['publishedTimeText']:
            time_runs = video_data['publishedTimeText']['runs']
            if time_runs and 'text' in time_runs[0]:
                published_at = time_runs[0]['text']
        
        # Extract basic video information from Oxylabs format
        video_info = {
            'video_id': video_data.get('videoId', ''),
            'title': title_text,
            'description': '',  # Not available in search results
            'channel_title': channel_title,
            'channel_id': '',  # Not available in search results
            'published_at': published_at,
            'thumbnails': video_data.get('thumbnail', {}),
            'view_count': view_count,
            'like_count': 0,  # Not available in search results
            'comment_count': 0,  # Not available in search results
            'duration': duration,
            'url': f"https://www.youtube.com/watch?v={video_data.get('videoId', '')}",
            'badges': video_data.get('badges', []),
            'published_time_text': published_at,
            'view_count_text': video_data.get('viewCountText', {}),
        }
        
        return video_info
        
    except Exception as e:
        logger.error(f"Error extracting video info: {e}")
        return {}


def save_processed_data(processed_data: Dict[str, Any], source_file_name: str) -> str:
    """
    Save processed data to the destination bucket.
    
    Args:
        processed_data: Processed video data
        source_file_name: Original source file name
        
    Returns:
        Path to the saved file in destination bucket
    """
    try:
        # Create destination bucket if it doesn't exist
        try:
            dest_bucket = get_storage_client().bucket(DEST_BUCKET)
            dest_bucket.reload()
        except Exception:
            logger.info(f"Creating destination bucket: {DEST_BUCKET}")
            dest_bucket = get_storage_client().create_bucket(DEST_BUCKET, project=PROJECT_ID)
        
        # Generate destination file name
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        base_name = os.path.splitext(os.path.basename(source_file_name))[0]
        dest_file_name = f"processed/{base_name}_{timestamp}.json"
        
        # Save processed data
        blob = dest_bucket.blob(dest_file_name)
        blob.upload_from_string(
            json.dumps(processed_data, indent=2, ensure_ascii=False),
            content_type='application/json'
        )
        
        logger.info(f"Processed data saved to: gs://{DEST_BUCKET}/{dest_file_name}")
        return dest_file_name
        
    except Exception as e:
        logger.error(f"Error saving processed data: {e}")
        raise


def read_source_data(bucket_name: str, file_name: str) -> Dict[str, Any]:
    """
    Read raw data from source bucket.
    
    Args:
        bucket_name: Source bucket name
        file_name: File name in the bucket
        
    Returns:
        Raw data as dictionary
    """
    try:
        bucket = get_storage_client().bucket(bucket_name)
        blob = bucket.blob(file_name)
        
        # Download and parse JSON
        content = blob.download_as_text()
        return json.loads(content)
        
    except Exception as e:
        logger.error(f"Error reading source data: {e}")
        raise


def youtube_data_processor(cloud_event: CloudEvent) -> str:
    """
    Cloud Function entry point - triggered by Cloud Storage events.
    
    Args:
        cloud_event: Cloud Event containing bucket and file information
        
    Returns:
        Success message
    """
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
        
        # Only process files in the raw_data/ folder
        if not file_name.startswith('raw_data/') or not file_name.endswith('.json'):
            logger.info(f"Skipping file not in raw_data/ folder or not JSON: {file_name}")
            return f"Skipped file not in raw_data/ folder or not JSON: {file_name}"
        
        logger.info(f"Processing file: gs://{bucket_name}/{file_name}")

        # Load JSON from GCS
        bucket = get_storage_client().bucket(bucket_name)
        blob = bucket.blob(file_name)
        raw_content = blob.download_as_text()
        raw_data = json.loads(raw_content)
        raw_data['source_file'] = file_name

        # Extract search query from filename
        search_query = extract_search_query_from_filename(file_name)
        raw_data['search_query'] = search_query

        if 'results' not in raw_data or not raw_data['results']:
            logger.error("No results found")
            return "No results found"

        first_result = raw_data['results'][0]
        if 'content' not in first_result:
            logger.error("No content found")
            return "No content found"

        processed_videos = []
        # Limit to first 5 videos to match max_results from search API
        max_videos_to_process = 5
        videos_to_process = first_result['content'][:max_videos_to_process]
        
        for video in videos_to_process:
            video_data = parse_video_data(video, raw_data)
            if not video_data:
                continue

            video_id = video_data.get("video_id")
            if not video_id:
                logger.warning("Missing video_id")
                continue

            # Save to GCS
            save_to_gcs(video_data, video_id, search_query)
            
            # Log the processed video data
            logger.info(f"Processed video: {video_id} - {video_data.get('title', 'No title')}")
            logger.info(f"  Channel: {video_data.get('channel_name', 'Unknown')}")
            logger.info(f"  Views: {video_data.get('views', 0)}")
            logger.info(f"  Duration: {video_data.get('duration', 'Unknown')}")
            logger.info(f"  Search Query: {video_data.get('search_query', 'Unknown')}")
            
            processed_videos.append(video_id)

        logger.info(f"Successfully processed {len(processed_videos)} videos from search: '{search_query}' (limited to {max_videos_to_process})")
        return f"Processed {len(processed_videos)} videos from search: '{search_query}'"

    except Exception as e:
        logger.error(f"Failed to process event: {e}")
        return f"Error: {str(e)}"


def parse_video_data(video: Dict[str, Any], raw_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        def get_text(obj):
            if isinstance(obj, dict):
                if 'simpleText' in obj:
                    return obj['simpleText']
                if 'runs' in obj:
                    return ' '.join(run.get('text', '') for run in obj['runs'])
            return ''

        def get_channel_id(obj):
            try:
                return obj['runs'][0]['navigationEndpoint']['browseEndpoint']['browseId']
            except:
                return ''

        def get_description(obj):
            if 'runs' in obj:
                return ' '.join(run.get('text', '') for run in obj['runs'])
            return ''

        video_info = {
            'video_id': video.get('videoId', ''),
            'title': get_text(video.get('title', {})),
            'channel_name': get_text(video.get('longBylineText', {})),
            'channel_id': get_channel_id(video.get('longBylineText', {})),
            'published_date': get_text(video.get('publishedTimeText', {})),
            'duration': get_text(video.get('lengthText', {})),
            'views': get_text(video.get('viewCountText', {})),
            'thumbnail_url': video.get('thumbnail', {}).get('thumbnails', [{}])[0].get('url', ''),
            'watch_url': f"https://www.youtube.com/watch?v={video.get('videoId', '')}",
            'description': get_description(video.get('descriptionSnippet', {})),
            'category': '',
            'language': 'en',
            'processed_at': datetime.utcnow().isoformat(),
            'raw_data_file': raw_data.get('source_file', ''),
            'search_query': raw_data.get('search_query', ''),
            'transcript_available': False,
            'transcript_file': None
        }

        # Convert views
        try:
            views = video_info['views'].replace(',', '').replace(' views', '')
            if 'K' in views:
                views = float(views.replace('K', '')) * 1_000
            elif 'M' in views:
                views = float(views.replace('M', '')) * 1_000_000
            video_info['views'] = int(views)
        except:
            video_info['views'] = 0

        # Convert duration
        try:
            parts = video_info['duration'].split(':')
            if len(parts) == 2:
                video_info['duration_seconds'] = int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                video_info['duration_seconds'] = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                video_info['duration_seconds'] = 0
        except:
            video_info['duration_seconds'] = 0

        return video_info

    except Exception as e:
        logger.error(f"Failed to parse video data: {e}")
        return None

def save_to_gcs(video_data: Dict[str, Any], video_id: str, search_query: str):
    """Save parsed video data to GCS"""
    try:
        bucket = storage_client.bucket(DEST_BUCKET)
        try:
            bucket.reload()
        except NotFound:
            storage_client.create_bucket(DEST_BUCKET, location='us-central1')
            logger.info(f"Created bucket: {DEST_BUCKET}")
        
        # Save individual video file
        blob = bucket.blob(f"processed/videos/{video_id}.json")
        blob.upload_from_string(json.dumps(video_data, indent=2), content_type='application/json')
        logger.info(f"Saved video to GCS: {video_id}")
        
        # Also save to processed folder with timestamp and search query
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        search_query_clean = search_query.replace(' ', '_')
        batch_blob = bucket.blob(f"processed/{search_query_clean}_{video_id}_{timestamp}.json")
        batch_blob.upload_from_string(json.dumps(video_data, indent=2), content_type='application/json')
        logger.info(f"Saved video batch to GCS: {search_query_clean}_{video_id}_{timestamp}")
        
    except Exception as e:
        logger.error(f"GCS save error: {e}")

# For local testing and Cloud Run HTTP server
if __name__ == "__main__":
    import flask
    from flask import Flask, request, jsonify
    import os
    
    app = Flask(__name__)
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({"status": "healthy", "service": "youtube-data-processor"})
    
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
                        source="//storage.googleapis.com/projects/_/buckets/youtube-search-data-bucket",
                        data=storage_event
                    )
                else:
                    return jsonify({"error": "Invalid Pub/Sub message format"}), 400
            else:
                # This is a direct HTTP request format
                logger.info("Direct HTTP request format")
                cloud_event = CloudEvent(
                    type="google.cloud.storage.object.v1.finalized",
                    source="//storage.googleapis.com/projects/_/buckets/youtube-search-data-bucket",
                    data=event_data
                )
            
            # Process the event
            result = youtube_data_processor(cloud_event)
            return jsonify({"result": result}), 200
            
        except Exception as e:
            logger.error(f"Error in process_webhook: {e}")
            return jsonify({"error": str(e)}), 500
    
    @app.route('/test', methods=['GET'])
    def test_endpoint():
        """Test endpoint for manual testing"""
        return jsonify({
            "message": "YouTube Data Processor is running",
            "endpoints": {
                "health": "/health",
                "process": "/process (POST)",
                "test": "/test"
            }
        })
    
    # Get port from environment variable (Cloud Run sets PORT=8080)
    port = int(os.environ.get('PORT', 8080))
    
    # Start the Flask server
    app.run(host='0.0.0.0', port=port, debug=False) 