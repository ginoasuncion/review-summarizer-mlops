import json
import os
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from flask import Flask, request, jsonify
from google.cloud import storage
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import openai
import base64
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'buoyant-yew-463209-k5')
SOURCE_BUCKET = os.environ.get('SOURCE_BUCKET', 'youtube-processed-data-bucket')
PRODUCTS_BUCKET = os.environ.get('PRODUCTS_BUCKET', 'youtube-processed-data-bucket')

# BigQuery Configuration
BIGQUERY_DATASET = os.environ.get('BIGQUERY_DATASET', 'youtube_reviews')
BIGQUERY_PROJECT = os.environ.get('BIGQUERY_PROJECT', PROJECT_ID)
PRODUCT_SUMMARIES_TABLE = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.product_summaries"
VIDEO_METADATA_TABLE = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.video_metadata"

# Processing Configuration
MIN_REVIEWS_PER_PRODUCT = int(os.environ.get('MIN_REVIEWS_PER_PRODUCT', '2'))
WAIT_TIME_MINUTES = int(os.environ.get('WAIT_TIME_MINUTES', '3'))
QUERY_BASED_PROCESSING = os.environ.get('QUERY_BASED_PROCESSING', 'true').lower() == 'true'
MIN_COMPLETION_RATE = float(os.environ.get('MIN_COMPLETION_RATE', '0.5'))  # 50% completion rate for timeout
QUERY_TIMEOUT_MINUTES = int(os.environ.get('QUERY_TIMEOUT_MINUTES', '5'))  # Default 5 minutes

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo')

# Flask app
app = Flask(__name__)

# Global state for tracking pending queries and products
pending_queries = {}
pending_products = {}
processing_lock = threading.Lock()

def extract_product_name(title: str, search_query: str) -> str:
    """Extract product name from video title and search query"""
    try:
        # Use the search query as the product name for grouping
        if search_query and len(search_query) > 3:
            # Clean up the search query
            cleaned_query = search_query.lower().strip()
            # Remove common prefixes like "raw data/youtube search"
            if cleaned_query.startswith('raw data/youtube search'):
                cleaned_query = cleaned_query.replace('raw data/youtube search', '').strip()
            return cleaned_query.title()
        
        # Fallback: use first few words of title
        words = title.split()[:4]
        return ' '.join(words).title()
        
    except Exception as e:
        logger.error(f"Error extracting product name: {e}")
        return "Unknown Product"

def get_all_video_metadata() -> List[Dict[str, Any]]:
    """Get all video metadata from GCS"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        videos = []
        
        # List all video files
        blobs = bucket.list_blobs(prefix='processed/videos/')
        
        for blob in blobs:
            if blob.name.endswith('.json'):
                try:
                    content = blob.download_as_text()
                    video_data = json.loads(content)
                    videos.append(video_data)
                        
                except Exception as e:
                    logger.warning(f"Error reading video file {blob.name}: {e}")
                    continue
        
        logger.info(f"Retrieved {len(videos)} total videos")
        return videos
        
    except Exception as e:
        logger.error(f"Error retrieving video metadata: {e}")
        return []

def get_videos_by_query(search_query: str) -> List[Dict[str, Any]]:
    """Get all videos for a specific search query"""
    try:
        all_videos = get_all_video_metadata()
        query_videos = []
        
        logger.info(f"Looking for videos with query: '{search_query}'")
        logger.info(f"Normalized search query: '{normalize_query(search_query)}'")
        logger.info(f"Total videos found: {len(all_videos)}")
        
        for i, video in enumerate(all_videos):
            video_query = video.get('search_query', '')
            video_id = video.get('video_id', '')
            title = video.get('title', '')
            
            normalized_video_query = normalize_query(video_query)
            normalized_search_query = normalize_query(search_query)
            
            logger.info(f"Video {i+1}: ID={video_id}, Title='{title[:50]}...', Query='{video_query}', Normalized='{normalized_video_query}'")
            
            # Normalize queries for comparison
            if normalized_video_query == normalized_search_query:
                query_videos.append(video)
                logger.info(f"✓ MATCH FOUND for video {video_id}")
            else:
                logger.info(f"✗ NO MATCH for video {video_id} (normalized: '{normalized_video_query}' != '{normalized_search_query}')")
        
        logger.info(f"Found {len(query_videos)} videos for query: {search_query}")
        return query_videos
        
    except Exception as e:
        logger.error(f"Error getting videos by query: {e}")
        return []

def normalize_query(query: str) -> str:
    """Normalize search query for comparison"""
    if not query:
        return ""
    # Remove common variations and normalize
    normalized = query.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized

def check_query_completion(search_query: str, query_start_time: Optional[datetime] = None) -> Dict[str, Any]:
    """Check if all videos from a search query have completed processing"""
    try:
        query_videos = get_videos_by_query(search_query)
        
        if not query_videos:
            return {
                'completed': False,
                'total_videos': 0,
                'completed_videos': 0,
                'pending_videos': 0,
                'reason': 'no_videos_found'
            }
        
        total_videos = len(query_videos)
        completed_videos = 0
        pending_videos = 0
        
        bucket = storage_client.bucket(SOURCE_BUCKET)
        
        for video in query_videos:
            video_id = video.get('video_id', '')
            
            # Check if transcript file exists
            transcript_blob = bucket.blob(f"transcripts/{video_id}.txt")
            has_transcript = transcript_blob.exists()
            
            # Check if summary file exists
            summary_blob = bucket.blob(f"summaries/{video_id}.txt")
            has_summary = summary_blob.exists()
            
            if has_transcript and has_summary:
                completed_videos += 1
                logger.info(f"Video {video_id} is complete (transcript: {has_transcript}, summary: {has_summary})")
            else:
                pending_videos += 1
                logger.info(f"Video {video_id} is pending (transcript: {has_transcript}, summary: {has_summary})")
        
        # Check if all videos are complete
        all_complete = completed_videos == total_videos and total_videos > 0
        
        # Check timeout condition (if query has been waiting too long)
        timeout_complete = False
        if query_start_time and not all_complete:
            current_time = datetime.now(timezone.utc)
            time_elapsed = current_time - query_start_time
            timeout_minutes = QUERY_TIMEOUT_MINUTES
            
            if time_elapsed.total_seconds() > (timeout_minutes * 60):
                # Consider complete if we have at least MIN_COMPLETION_RATE completion and enough time has passed
                completion_rate = completed_videos / total_videos if total_videos > 0 else 0
                if completion_rate >= MIN_COMPLETION_RATE:  # 50% completion rate by default
                    timeout_complete = True
                    logger.info(f"Query '{search_query}' timed out after {timeout_minutes} minutes with {completion_rate:.1%} completion rate (threshold: {MIN_COMPLETION_RATE:.1%})")
                else:
                    logger.info(f"Query '{search_query}' timed out but completion rate {completion_rate:.1%} below threshold {MIN_COMPLETION_RATE:.1%}")
        
        completed = all_complete or timeout_complete
        
        logger.info(f"Query completion status for '{search_query}': {completed_videos}/{total_videos} videos complete (timeout: {timeout_complete})")
        
        return {
            'completed': completed,
            'total_videos': total_videos,
            'completed_videos': completed_videos,
            'pending_videos': pending_videos,
            'search_query': search_query,
            'timeout_complete': timeout_complete,
            'completion_rate': completed_videos / total_videos if total_videos > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error checking query completion: {e}")
        return {
            'completed': False,
            'total_videos': 0,
            'completed_videos': 0,
            'pending_videos': 0,
            'reason': 'error'
        }

def group_videos_by_product(videos: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group videos by product name"""
    try:
        product_groups = {}
        
        for video in videos:
            title = video.get('title', '')
            search_query = video.get('search_query', '')
            
            # Extract product name
            product_name = extract_product_name(title, search_query)
            
            # Group by product name
            if product_name not in product_groups:
                product_groups[product_name] = []
            
            product_groups[product_name].append(video)
        
        logger.info(f"Found {len(product_groups)} total product groups")
        return product_groups
        
    except Exception as e:
        logger.error(f"Error grouping videos by product: {e}")
        return {}

def get_summary_content(video_id: str) -> Optional[str]:
    """Get summary content from GCS"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        summary_blob = bucket.blob(f"summaries/{video_id}.txt")
        
        if not summary_blob.exists():
            logger.warning(f"Summary file not found: {video_id}")
            return None
        
        content = summary_blob.download_as_text()
        return content
        
    except Exception as e:
        logger.error(f"Error retrieving summary for video {video_id}: {e}")
        return None

def get_transcript_content(video_id: str) -> Optional[str]:
    """Get transcript content from GCS"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        transcript_blob = bucket.blob(f"transcripts/{video_id}.txt")
        
        if not transcript_blob.exists():
            logger.warning(f"Transcript file not found: {video_id}")
            return None
        
        content = transcript_blob.download_as_text()
        return content
        
    except Exception as e:
        logger.error(f"Error retrieving transcript for video {video_id}: {e}")
        return None

def generate_product_summary(product_name: str, videos: List[Dict[str, Any]], search_query: str) -> Optional[str]:
    """Generate comprehensive product summary from multiple reviews"""
    try:
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not configured")
            return None
        
        # Set up OpenAI client
        openai.api_key = OPENAI_API_KEY
        
        # Collect all summaries, transcripts, and video info
        video_data = []
        total_views = 0
        
        for video in videos:
            video_id = video.get('video_id', '')
            title = video.get('title', '')
            channel = video.get('channel_name', '')
            views = video.get('views', 0)
            duration = video.get('duration', '')
            
            summary_content = get_summary_content(video_id)
            transcript_content = get_transcript_content(video_id)
            
            if summary_content and transcript_content:
                video_data.append({
                    'title': title,
                    'channel': channel,
                    'views': views,
                    'duration': duration,
                    'summary': summary_content,
                    'transcript': transcript_content
                })
                total_views += views
        
        if not video_data:
            logger.warning(f"No complete data available for product: {product_name}")
            return None
        
        # Create comprehensive prompt with both summaries and transcripts
        reviews_text = ""
        for i, video in enumerate(video_data, 1):
            reviews_text += f"""
Review {i}:
- Video: {video['title']}
- Channel: {video['channel']}
- Views: {video['views']:,}
- Duration: {video['duration']}

Summary:
{video['summary']}

Full Transcript:
{video['transcript'][:1000]}...  # First 1000 chars of transcript

---
"""
        
        prompt = f"""
You are an expert product analyst. Based on the following {len(video_data)} YouTube reviews of the {product_name}, create a comprehensive product analysis.

Original Search Query: {search_query}
Product: {product_name}
Total Reviews Analyzed: {len(video_data)}
Total Views: {total_views:,}

Individual Reviews (with summaries and transcript excerpts):
{reviews_text}

Please provide a comprehensive analysis that includes:

1. **Product Overview**: What is this product and its main features?

2. **Consensus Analysis**: What do most reviewers agree on? (pros and cons)

3. **Key Strengths**: What are the most commonly praised aspects?

4. **Common Concerns**: What issues or drawbacks are frequently mentioned?

5. **Price-Performance**: How do reviewers rate the value for money?

6. **Target Audience**: Who would benefit most from this product?

7. **Comparison Insights**: How does it compare to alternatives (if mentioned)?

8. **Overall Recommendation**: What's the general consensus on whether to buy?

9. **Reviewer Credibility**: Note the diversity of reviewers and their expertise levels.

10. **Detailed Insights**: Based on the full transcripts, provide deeper analysis of specific features, testing methods, and real-world usage experiences.

Format the analysis in a clear, structured manner with bullet points where appropriate.
Keep it comprehensive but concise (around 500-700 words).
Focus on providing actionable insights for potential buyers.
Use specific examples from the transcripts when relevant.
"""

        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert product analyst who synthesizes multiple reviews and transcripts into comprehensive, actionable insights."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.3
        )
        
        summary = response.choices[0].message.content.strip()
        logger.info(f"Generated product summary for {product_name} ({len(summary)} characters)")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating product summary: {e}")
        return None

def save_product_summary(product_name: str, summary: str, videos: List[Dict[str, Any]], search_query: str) -> str:
    """Save product summary to GCS"""
    try:
        bucket = storage_client.bucket(PRODUCTS_BUCKET)
        
        # Create products folder if it doesn't exist
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        product_name_clean = re.sub(r'[^\w\s-]', '', product_name).replace(' ', '_')
        search_query_clean = re.sub(r'[^\w\s-]', '', search_query).replace(' ', '_')
        file_name = f"products/{search_query_clean}_{product_name_clean}_{timestamp}.txt"
        
        blob = bucket.blob(file_name)
        blob.upload_from_string(summary, content_type='text/plain')
        
        logger.info(f"Saved product summary to: gs://{PRODUCTS_BUCKET}/{file_name}")
        return f"gs://{PRODUCTS_BUCKET}/{file_name}"
        
    except Exception as e:
        logger.error(f"Error saving product summary: {e}")
        return ""

def save_product_metadata(product_name: str, summary_file: str, videos: List[Dict[str, Any]], search_query: str, transcript_file: str = ""):
    """Save product metadata to GCS"""
    try:
        bucket = storage_client.bucket(PRODUCTS_BUCKET)
        
        # Create metadata structure
        product_metadata = {
            'product_name': product_name,
            'search_query': search_query,
            'summary_file': summary_file,
            'transcript_file': transcript_file,
            'total_reviews': len(videos),
            'total_views': sum(v.get('views', 0) for v in videos),
            'average_views': sum(v.get('views', 0) for v in videos) // len(videos),
            'reviewers': [v.get('channel_name', 'Unknown') for v in videos],
            'video_ids': [v.get('video_id', '') for v in videos],
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'processing_strategy': 'query_based' if QUERY_BASED_PROCESSING else 'individual'
        }
        
        # Save metadata
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        product_name_clean = re.sub(r'[^\w\s-]', '', product_name).replace(' ', '_')
        search_query_clean = re.sub(r'[^\w\s-]', '', search_query).replace(' ', '_')
        metadata_file = f"products/{search_query_clean}_{product_name_clean}_{timestamp}_metadata.json"
        
        blob = bucket.blob(metadata_file)
        blob.upload_from_string(
            json.dumps(product_metadata, indent=2),
            content_type='application/json'
        )
        
        logger.info(f"Saved product metadata to: gs://{PRODUCTS_BUCKET}/{metadata_file}")
        return f"gs://{PRODUCTS_BUCKET}/{metadata_file}"
        
    except Exception as e:
        logger.error(f"Error saving product metadata: {e}")
        return ""

def insert_product_summary_to_bigquery(product_name: str, summary_content: str, videos: List[Dict[str, Any]], search_query: str, summary_file: str):
    """Insert product summary data to BigQuery with duplicate prevention"""
    try:
        # Calculate total views
        total_views = sum(video.get('view_count', 0) for video in videos)
        average_views = total_views / len(videos) if videos else 0
        total_reviews = len(videos)
        
        # Check if product already exists
        check_query = f"""
        SELECT total_reviews, processed_at
        FROM `{PRODUCT_SUMMARIES_TABLE}`
        WHERE product_name = '{product_name}' AND search_query = '{search_query}'
        ORDER BY processed_at DESC
        LIMIT 1
        """
        
        try:
            query_job = bigquery_client.query(check_query)
            existing_results = list(query_job.result())
            
            if existing_results:
                existing_reviews = existing_results[0].total_reviews
                existing_processed_at = existing_results[0].processed_at
                
                # Only update if we have more reviews or if it's been more than 1 hour
                current_time = datetime.now(timezone.utc)
                time_diff = current_time - existing_processed_at.replace(tzinfo=timezone.utc)
                
                if total_reviews <= existing_reviews and time_diff.total_seconds() < 3600:  # 1 hour
                    logger.info(f"Product {product_name} already exists with {existing_reviews} reviews (current: {total_reviews}), skipping insert")
                    return True
                else:
                    logger.info(f"Updating product {product_name} - existing: {existing_reviews} reviews, new: {total_reviews} reviews")
        except Exception as e:
            logger.warning(f"Error checking existing product {product_name}: {e}")
            # Continue with insert if check fails
        
        # Prepare row data
        row = {
            'product_name': product_name,
            'search_query': search_query,
            'summary_content': summary_content,
            'total_reviews': total_reviews,
            'total_views': total_views,
            'average_views': average_views,
            'processed_at': datetime.now(timezone.utc).isoformat(),
            'summary_file': summary_file,
            'processing_strategy': 'query_based'
        }
        
        # Insert into BigQuery
        table = bigquery_client.get_table(PRODUCT_SUMMARIES_TABLE)
        errors = bigquery_client.insert_rows_json(table, [row])
        
        if errors:
            logger.error(f"BigQuery insert errors for product {product_name}: {errors}")
            return False
        else:
            logger.info(f"Successfully inserted product summary to BigQuery: {product_name}")
            return True
            
    except Exception as e:
        logger.error(f"Error inserting product summary to BigQuery: {e}")
        return False

def insert_video_metadata_to_bigquery(videos: List[Dict[str, Any]]):
    """Insert video metadata to BigQuery with duplicate prevention"""
    try:
        if not videos:
            logger.warning("No video metadata to insert")
            return False
        
        # Get the search query from the first video
        search_query = videos[0].get('search_query', '')
        if not search_query:
            logger.warning("No search query found in videos")
            return False
        
        # Check if videos for this search query already exist
        check_query = f"""
        SELECT COUNT(*) as existing_count
        FROM `{VIDEO_METADATA_TABLE}`
        WHERE search_query = '{search_query}'
        """
        
        try:
            query_job = bigquery_client.query(check_query)
            existing_results = list(query_job.result())
            
            if existing_results and existing_results[0].existing_count > 0:
                logger.info(f"Video metadata for search query '{search_query}' already exists ({existing_results[0].existing_count} records), skipping insert")
                return True
        except Exception as e:
            logger.warning(f"Error checking existing video metadata for search query {search_query}: {e}")
            # Continue with insert if check fails
        
        rows = []
        current_time = datetime.now(timezone.utc).isoformat()
        
        for video in videos:
            row = {
                'video_id': video.get('video_id', ''),
                'title': video.get('title', ''),
                'channel_name': video.get('channel_name', ''),
                'view_count': video.get('view_count', 0),
                'duration': video.get('duration', ''),
                'url': video.get('url', ''),
                'search_query': video.get('search_query', ''),
                'transcript_available': video.get('transcript_available', False),
                'summary_available': video.get('summary_available', False),
                'transcript_file': f"gs://{SOURCE_BUCKET}/transcripts/{video.get('video_id', '')}.txt" if video.get('transcript_available') else None,
                'summary_file': f"gs://{SOURCE_BUCKET}/summaries/{video.get('video_id', '')}.txt" if video.get('summary_available') else None,
                'processed_at': current_time
            }
            rows.append(row)
        
        if rows:
            # Insert into BigQuery
            table = bigquery_client.get_table(VIDEO_METADATA_TABLE)
            errors = bigquery_client.insert_rows_json(table, rows)
            
            if errors:
                logger.error(f"BigQuery insert errors for video metadata: {errors}")
                return False
            else:
                logger.info(f"Successfully inserted {len(rows)} video metadata records to BigQuery")
                return True
        else:
            logger.warning("No video metadata to insert")
            return False
            
    except Exception as e:
        logger.error(f"Error inserting video metadata to BigQuery: {e}")
        return False

def process_query_complete(search_query: str):
    """Process a completed search query and create product summaries"""
    try:
        logger.info(f"Processing completed query: {search_query}")
        
        # Get all videos for this query
        query_videos = get_videos_by_query(search_query)
        if not query_videos:
            logger.warning(f"No videos found for query: {search_query}")
            return False
        
        # Filter videos to only include those with both transcript and summary
        bucket = storage_client.bucket(SOURCE_BUCKET)
        complete_videos = []
        incomplete_videos = []
        
        for video in query_videos:
            video_id = video.get('video_id', '')
            
            # Check if transcript file exists
            transcript_blob = bucket.blob(f"transcripts/{video_id}.txt")
            has_transcript = transcript_blob.exists()
            
            # Check if summary file exists
            summary_blob = bucket.blob(f"summaries/{video_id}.txt")
            has_summary = summary_blob.exists()
            
            if has_transcript and has_summary:
                complete_videos.append(video)
                logger.info(f"Video {video_id} is complete and will be processed")
            else:
                incomplete_videos.append(video)
                logger.info(f"Video {video_id} is incomplete (transcript: {has_transcript}, summary: {has_summary}) and will be skipped")
        
        if not complete_videos:
            logger.warning(f"No complete videos found for query: {search_query}")
            return False
        
        logger.info(f"Processing {len(complete_videos)} complete videos out of {len(query_videos)} total videos for query: {search_query}")
        
        # Group complete videos by product
        product_groups = group_videos_by_product(complete_videos)
        if not product_groups:
            logger.warning(f"No product groups found for query: {search_query}")
            return False
        
        # Process each product group
        processed_products = []
        for product_name, videos in product_groups.items():
            try:
                # Only process if we have enough reviews
                if len(videos) >= MIN_REVIEWS_PER_PRODUCT:
                    logger.info(f"Processing product: {product_name} with {len(videos)} complete reviews")
                    
                    # Generate comprehensive summary
                    summary = generate_product_summary(product_name, videos, search_query)
                    if not summary:
                        logger.warning(f"Failed to generate summary for product: {product_name}")
                        continue
                    
                    # Save summary and metadata
                    summary_file = save_product_summary(product_name, summary, videos, search_query)
                    
                    # Save concatenated transcripts
                    transcript_file = save_concatenated_transcripts(product_name, videos, search_query)
                    
                    metadata_file = save_product_metadata(product_name, summary_file, videos, search_query, transcript_file)
                    
                    if summary_file and metadata_file:
                        # Insert to BigQuery
                        bigquery_success = insert_product_summary_to_bigquery(product_name, summary, videos, search_query, summary_file)
                        if bigquery_success:
                            logger.info(f"Successfully inserted product summary to BigQuery: {product_name}")
                        else:
                            logger.warning(f"Failed to insert product summary to BigQuery: {product_name}")
                        
                        processed_products.append({
                            'product_name': product_name,
                            'review_count': len(videos),
                            'summary_file': summary_file,
                            'transcript_file': transcript_file,
                            'metadata_file': metadata_file
                        })
                        
                        logger.info(f"Successfully processed product: {product_name}")
                    else:
                        logger.warning(f"Failed to save files for product: {product_name}")
                else:
                    logger.info(f"Skipping product {product_name} - only {len(videos)} complete reviews (need {MIN_REVIEWS_PER_PRODUCT})")
                
            except Exception as e:
                logger.error(f"Error processing product {product_name}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(processed_products)} products for query: {search_query}")
        
        # Insert all video metadata to BigQuery (including incomplete ones for reference)
        if query_videos:
            bigquery_video_success = insert_video_metadata_to_bigquery(query_videos)
            if bigquery_video_success:
                logger.info(f"Successfully inserted {len(query_videos)} video metadata records to BigQuery")
            else:
                logger.warning(f"Failed to insert video metadata to BigQuery for query: {search_query}")
        
        return len(processed_products) > 0
        
    except Exception as e:
        logger.error(f"Error processing completed query {search_query}: {e}")
        return False

def query_monitoring_worker():
    """Background worker for monitoring query completion"""
    while True:
        try:
            with processing_lock:
                current_time = datetime.now(timezone.utc)
                queries_to_process = []
                
                # Check which queries are ready for processing
                for search_query, query_info in list(pending_queries.items()):
                    last_update = query_info['last_update']
                    wait_until = last_update + timedelta(minutes=WAIT_TIME_MINUTES)
                    
                    if current_time >= wait_until:
                        # Check if query is complete (pass start time for timeout checking)
                        completion_status = check_query_completion(search_query, last_update)
                        
                        if completion_status['completed']:
                            queries_to_process.append(search_query)
                            del pending_queries[search_query]
                            logger.info(f"Query {search_query} is complete and ready for processing")
                        else:
                            logger.info(f"Query {search_query} still has {completion_status['pending_videos']} pending videos")
            
            # Also check for any queries that might have been missed (not in pending list)
            # Get all unique search queries from video metadata
            all_videos = get_all_video_metadata()
            all_queries = set()
            for video in all_videos:
                search_query = video.get('search_query', '')
                if search_query:
                    all_queries.add(search_query)
            
            # Check each query for completion (use current time as start time for missed queries)
            for search_query in all_queries:
                if search_query not in pending_queries:
                    completion_status = check_query_completion(search_query, current_time)
                    if completion_status['completed']:
                        logger.info(f"Found completed query not in pending list: {search_query}")
                        queries_to_process.append(search_query)
            
            # Process completed queries
            for search_query in queries_to_process:
                process_query_complete(search_query)
            
            # Sleep for a short time before next check
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            logger.error(f"Error in query monitoring worker: {e}")
            time.sleep(60)  # Wait longer on error

def add_query_to_monitoring(search_query: str):
    """Add a search query to the monitoring queue"""
    try:
        with processing_lock:
            if search_query not in pending_queries:
                pending_queries[search_query] = {
                    'last_update': datetime.now(timezone.utc),
                    'videos': []
                }
                logger.info(f"Added query to monitoring: {search_query}")
            else:
                # Update last update time
                pending_queries[search_query]['last_update'] = datetime.now(timezone.utc)
                logger.info(f"Updated query monitoring: {search_query}")
        
    except Exception as e:
        logger.error(f"Error adding query to monitoring: {e}")

def product_aggregator(cloud_event):
    """Aggregate multiple video reviews into product summaries"""
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
        
        # Process different file types
        if file_name.startswith('processed/videos/') and file_name.endswith('.json'):
            # New video metadata uploaded
            video_id = file_name.replace('processed/videos/', '').replace('.json', '')
            video_metadata = get_video_metadata_by_id(video_id)
            
            if video_metadata:
                search_query = video_metadata.get('search_query', '')
                if search_query:
                    add_query_to_monitoring(search_query)
                    logger.info(f"Added video {video_id} to query monitoring: {search_query}")
        
        elif file_name.startswith('transcripts/') and file_name.endswith('.txt'):
            # New transcript uploaded - check if this completes a query
            video_id = file_name.replace('transcripts/', '').replace('.txt', '')
            video_metadata = get_video_metadata_by_id(video_id)
            
            if video_metadata:
                search_query = video_metadata.get('search_query', '')
                if search_query:
                    # Check if query is now complete
                    completion_status = check_query_completion(search_query, datetime.now(timezone.utc))
                    logger.info(f"Transcript uploaded for {video_id}, query {search_query} status: {completion_status}")
                    
                    # If query is complete, process it immediately
                    if completion_status['completed']:
                        logger.info(f"Query {search_query} is complete, triggering processing")
                        process_query_complete(search_query)
        
        elif file_name.startswith('summaries/') and file_name.endswith('.txt'):
            # New summary uploaded - check if this completes a query
            video_id = file_name.replace('summaries/', '').replace('.txt', '')
            video_metadata = get_video_metadata_by_id(video_id)
            
            if video_metadata:
                search_query = video_metadata.get('search_query', '')
                if search_query:
                    # Check if query is now complete
                    completion_status = check_query_completion(search_query, datetime.now(timezone.utc))
                    logger.info(f"Summary uploaded for {video_id}, query {search_query} status: {completion_status}")
                    
                    # If query is complete, process it immediately
                    if completion_status['completed']:
                        logger.info(f"Query {search_query} is complete, triggering processing")
                        process_query_complete(search_query)
        
        # Get current monitoring status
        with processing_lock:
            pending_count = len(pending_queries)
        
        return {
            'status': 'monitoring',
            'file_processed': file_name,
            'pending_queries': pending_count,
            'processing_strategy': 'query_based' if QUERY_BASED_PROCESSING else 'individual'
        }

    except Exception as e:
        logger.error(f"Error in product_aggregator: {e}")
        return {'status': 'error', 'error': str(e)}

def get_video_metadata_by_id(video_id: str) -> Optional[Dict[str, Any]]:
    """Get video metadata by video ID"""
    try:
        bucket = storage_client.bucket(SOURCE_BUCKET)
        video_blob = bucket.blob(f"processed/videos/{video_id}.json")
        
        if not video_blob.exists():
            logger.warning(f"Video metadata file not found: {video_id}")
            return None
        
        content = video_blob.download_as_text()
        metadata = json.loads(content)
        return metadata
        
    except Exception as e:
        logger.error(f"Error retrieving metadata for video {video_id}: {e}")
        return None

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    with processing_lock:
        pending_count = len(pending_queries)
    
    return jsonify({
        'service': 'youtube-product-aggregator',
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'pending_queries': pending_count,
        'processing_strategy': 'query_based' if QUERY_BASED_PROCESSING else 'individual',
        'min_reviews_per_product': MIN_REVIEWS_PER_PRODUCT,
        'wait_time_minutes': WAIT_TIME_MINUTES
    })

@app.route('/pending', methods=['GET'])
def get_pending_queries():
    """Get information about pending queries"""
    with processing_lock:
        pending_info = {}
        for search_query, info in pending_queries.items():
            completion_status = check_query_completion(search_query)
            pending_info[search_query] = {
                'last_update': info['last_update'].isoformat(),
                'wait_until': (info['last_update'] + timedelta(minutes=WAIT_TIME_MINUTES)).isoformat(),
                'completion_status': completion_status
            }
    
    return jsonify({
        'pending_queries': pending_info,
        'total_pending_queries': len(pending_queries),
        'min_reviews_required': MIN_REVIEWS_PER_PRODUCT,
        'wait_time_minutes': WAIT_TIME_MINUTES
    })

@app.route('/process', methods=['POST'])
def process_webhook():
    """HTTP webhook endpoint for Cloud Storage events"""
    try:
        # Get the request data
        request_data = request.get_json()
        
        if not request_data:
            logger.error("No JSON data received")
            return jsonify({'error': 'No JSON data received'}), 400
        
        # Handle Pub/Sub message format
        if 'message' in request_data:
            # Decode Pub/Sub message
            message_data = request_data['message']
            if 'data' in message_data:
                # Decode base64 data
                decoded_data = base64.b64decode(message_data['data']).decode('utf-8')
                cloud_event_data = json.loads(decoded_data)
                
                # Create a mock CloudEvent object
                class MockCloudEvent:
                    def __init__(self, data):
                        self.data = data
                
                cloud_event = MockCloudEvent(cloud_event_data)
            else:
                logger.error("No data in Pub/Sub message")
                return jsonify({'error': 'No data in Pub/Sub message'}), 400
        else:
            # Direct Cloud Storage event
            class MockCloudEvent:
                def __init__(self, data):
                    self.data = data
            
            cloud_event = MockCloudEvent(request_data)
        
        # Process the event
        result = product_aggregator(cloud_event)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/force-process', methods=['POST'])
def force_process_query():
    """Force process a query even if not all videos are complete"""
    try:
        data = request.get_json()
        search_query = data.get('search_query')
        min_completed = data.get('min_completed', 1)  # Default to 1 instead of MIN_REVIEWS_PER_PRODUCT
        
        if not search_query:
            return jsonify({'error': 'search_query is required'}), 400
        
        # Check current completion status
        completion_status = check_query_completion(search_query)
        
        logger.info(f"Force processing query: {search_query}")
        logger.info(f"Completion status: {completion_status['completed_videos']}/{completion_status['total_videos']} videos complete")
        logger.info(f"Minimum required: {min_completed}")
        
        if completion_status['completed_videos'] < min_completed:
            return jsonify({
                'success': False,
                'error': f'Not enough completed videos. Need at least {min_completed}, have {completion_status["completed_videos"]}',
                'query': search_query,
                'completed_videos': completion_status['completed_videos'],
                'total_videos': completion_status['total_videos']
            }), 400
        
        # Force process the query
        logger.info(f"Force processing query: {search_query} with {completion_status['completed_videos']} completed videos")
        success = process_query_complete(search_query)
        
        return jsonify({
            'success': success,
            'query': search_query,
            'completed_videos': completion_status['completed_videos'],
            'total_videos': completion_status['total_videos'],
            'message': f"Processed query with {completion_status['completed_videos']} complete videos"
        })
        
    except Exception as e:
        logger.error(f"Error in force_process_query: {e}")
        return jsonify({'error': str(e)}), 500

def save_concatenated_transcripts(product_name: str, videos: List[Dict[str, Any]], search_query: str) -> str:
    """Concatenate and save all transcripts for a product to GCS"""
    try:
        bucket = storage_client.bucket(PRODUCTS_BUCKET)
        
        # Collect all transcripts
        concatenated_transcripts = []
        total_transcripts = 0
        
        for i, video in enumerate(videos, 1):
            video_id = video.get('video_id', '')
            title = video.get('title', '')
            channel = video.get('channel_name', '')
            views = video.get('views', 0)
            duration = video.get('duration', '')
            
            transcript_content = get_transcript_content(video_id)
            
            if transcript_content:
                # Add video metadata header
                video_header = f"""
{'='*80}
VIDEO {i}: {title}
Channel: {channel}
Views: {views:,}
Duration: {duration}
Video ID: {video_id}
{'='*80}

"""
                concatenated_transcripts.append(video_header)
                concatenated_transcripts.append(transcript_content)
                concatenated_transcripts.append("\n\n")
                total_transcripts += 1
        
        if not concatenated_transcripts:
            logger.warning(f"No transcripts available for product: {product_name}")
            return ""
        
        # Create the full concatenated content
        full_content = "".join(concatenated_transcripts)
        
        # Add overall header
        overall_header = f"""
CONCATENATED TRANSCRIPTS FOR PRODUCT REVIEWS
{'='*80}
Product: {product_name}
Search Query: {search_query}
Total Videos: {len(videos)}
Videos with Transcripts: {total_transcripts}
Generated: {datetime.now(timezone.utc).isoformat()}
{'='*80}

"""
        
        final_content = overall_header + full_content
        
        # Save to GCS
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        product_name_clean = re.sub(r'[^\w\s-]', '', product_name).replace(' ', '_')
        search_query_clean = re.sub(r'[^\w\s-]', '', search_query).replace(' ', '_')
        file_name = f"products/{search_query_clean}_{product_name_clean}_{timestamp}_transcripts.txt"
        
        blob = bucket.blob(file_name)
        blob.upload_from_string(final_content, content_type='text/plain')
        
        logger.info(f"Saved concatenated transcripts to: gs://{PRODUCTS_BUCKET}/{file_name}")
        return f"gs://{PRODUCTS_BUCKET}/{file_name}"
        
    except Exception as e:
        logger.error(f"Error saving concatenated transcripts: {e}")
        return ""

# Start the query monitoring worker thread
if QUERY_BASED_PROCESSING:
    worker_thread = threading.Thread(target=query_monitoring_worker, daemon=True)
    worker_thread.start()
    logger.info(f"Started query monitoring worker (wait time: {WAIT_TIME_MINUTES} minutes, min reviews: {MIN_REVIEWS_PER_PRODUCT})")

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 