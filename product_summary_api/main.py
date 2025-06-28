# Updated with new BigQuery fields: product_name, total_reviews, total_views, average_views
import json
import os
import logging
import openai
import time
import random
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from flask import Flask, request, jsonify
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound
import requests
import functions_framework

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
bigquery_client = bigquery.Client()
storage_client = storage.Client()

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'buoyant-yew-463209-k5')
BIGQUERY_DATASET = os.environ.get('BIGQUERY_DATASET', 'youtube_reviews')
BIGQUERY_PROJECT = os.environ.get('BIGQUERY_PROJECT', PROJECT_ID)
VIDEO_METADATA_TABLE = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.video_metadata"
PRODUCT_SUMMARIES_TABLE = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.product_summaries"

# OpenAI Configuration
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o')

# Flask app
app = Flask(__name__)

# New configuration
BUCKET_NAME = "youtube-processed-data-bucket"
LLM_JUDGE_API_URL = "https://llm-judge-api-nxbmt7mfiq-uc.a.run.app/evaluate"

def get_video_summaries_by_query(search_query: str) -> List[Dict[str, Any]]:
    """Get all video summaries for a specific search query from BigQuery"""
    try:
        query = f"""
        SELECT 
            video_id,
            title,
            channel_title,
            view_count,
            summary_content,
            processed_at
        FROM `{VIDEO_METADATA_TABLE}`
        WHERE search_query = @search_query 
        AND summary_available = true 
        AND summary_content IS NOT NULL
        ORDER BY view_count DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("search_query", "STRING", search_query),
            ]
        )
        
        query_job = bigquery_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        videos = []
        for row in results:
            videos.append({
                'video_id': row.video_id,
                'title': row.title,
                'channel_title': row.channel_title,
                'view_count': row.view_count,
                'summary_content': row.summary_content,
                'processed_at': row.processed_at.isoformat() if row.processed_at else None
            })
        
        logger.info(f"Found {len(videos)} videos with summaries for query: {search_query}")
        return videos
        
    except Exception as e:
        logger.error(f"Error getting video summaries for query {search_query}: {e}")
        return []

def check_existing_product_summary(search_query: str) -> Optional[Dict[str, Any]]:
    """Check if a product summary already exists for the search query"""
    try:
        query = f"""
        SELECT 
            product_name,
            search_query,
            summary_content,
            total_reviews,
            total_views,
            average_views,
            created_at,
            video_count
        FROM `{PRODUCT_SUMMARIES_TABLE}`
        WHERE search_query = @search_query
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("search_query", "STRING", search_query),
            ]
        )
        
        query_job = bigquery_client.query(query, job_config=job_config)
        results = list(query_job.result())
        
        if results:
            row = results[0]
            return {
                'product_name': row.product_name,
                'search_query': row.search_query,
                'summary_content': row.summary_content,
                'total_reviews': row.total_reviews,
                'total_views': row.total_views,
                'average_views': row.average_views,
                'created_at': row.created_at.isoformat() if row.created_at else None,
                'video_count': row.video_count
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error checking existing product summary for query {search_query}: {e}")
        return None

def generate_unified_product_summary(search_query: str, videos: List[Dict[str, Any]], max_retries: int = 3) -> Optional[Dict[str, Any]]:
    """Generate a unified product summary from multiple video summaries using ChatGPT with retry logic"""
    for attempt in range(max_retries + 1):
        try:
            if not OPENAI_API_KEY:
                logger.error("OpenAI API key not configured")
                return None
            
            # Set up OpenAI client (new style)
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            # Prepare the concatenated summaries
            concatenated_summaries = []
            total_views = 0
            
            for i, video in enumerate(videos, 1):
                video_id = video['video_id']
                title = video['title']
                channel = video['channel_title']
                views = video['view_count']
                summary = video['summary_content']
                
                total_views += views
                
                video_header = f"""
{'='*80}
VIDEO {i}: {title}
Channel: {channel}
Views: {views:,}
Video ID: {video_id}
{'='*80}

"""
                concatenated_summaries.append(video_header)
                concatenated_summaries.append(summary)
                concatenated_summaries.append("\n\n")
            
            full_content = "".join(concatenated_summaries)
            
            # Create prompt for unified summarization
            prompt = f"""
Please create a comprehensive, unified product summary based on the following YouTube video reviews.

Search Query: {search_query}
Total Videos: {len(videos)}
Total Views: {total_views:,}

Video Reviews:
{full_content}

Please provide a structured, unified summary that includes:

1. **Product Overview**: What is the product and what is it known for?
2. **Key Features & Benefits**: What are the main features and benefits mentioned across all reviews?
3. **Pros & Cons**: What are the most commonly mentioned positive and negative aspects?
4. **Quality & Durability**: What do reviewers say about build quality and longevity?
5. **Comfort & Fit**: What are the sizing and comfort recommendations?
6. **Value for Money**: What do reviewers think about the price-to-value ratio?
7. **Target Audience**: Who would benefit most from this product?
8. **Overall Consensus**: What is the general sentiment and recommendation across all reviews?

Format the summary in a clear, structured manner with bullet points where appropriate.
Keep the summary comprehensive but concise (around 400-500 words).
Focus on providing actionable insights for potential buyers.
"""

            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that creates unified product summaries from multiple YouTube video reviews, focusing on providing clear, actionable insights for potential buyers."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated unified product summary for query: {search_query} ({len(summary)} characters)")
            
            # Always evaluate product summaries with LLM judge since they're the final output
            llm_scores = call_llm_judge_api(
                summary_content=summary,
                search_query=search_query
            )
            
            return {
                'summary': summary,
                'llm_scores': llm_scores
            }
            
        except openai.RateLimitError as e:
            if attempt < max_retries:
                # Calculate backoff time (exponential backoff with jitter)
                backoff_time = min(2 ** attempt + (time.time() % 1), 60)  # Cap at 60 seconds
                logger.warning(f"Rate limit hit during product summary generation, retrying in {backoff_time:.1f} seconds (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(backoff_time)
                continue
            else:
                logger.error(f"Rate limit exceeded after {max_retries + 1} attempts during product summary generation: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating unified product summary: {e}")
            return None
    
    return None

def extract_product_name(search_query: str) -> str:
    """Extract product name from search query"""
    try:
        # Clean up the search query
        cleaned_query = search_query.lower().strip()
        # Remove common suffixes
        for suffix in [' review', ' reviews', ' comparison', ' vs', ' versus']:
            if cleaned_query.endswith(suffix):
                cleaned_query = cleaned_query[:-len(suffix)]
        return cleaned_query.title()
    except Exception as e:
        logger.error(f"Error extracting product name: {e}")
        return search_query.title()

def insert_product_summary_to_bigquery(product_name: str, search_query: str, summary_content: str, videos: List[Dict[str, Any]], llm_scores: Optional[Dict[str, float]] = None):
    """Insert the unified product summary into BigQuery"""
    try:
        video_ids = [video['video_id'] for video in videos]
        
        # Prepare the row data
        total_reviews = len(videos)
        total_views = sum(video.get('view_count', 0) for video in videos)
        average_views = total_views / total_reviews if total_reviews > 0 else 0
        row = {
            'product_name': extract_product_name(search_query),
            'search_query': search_query,
            'summary_content': summary_content,
            'video_count': total_reviews,
            'video_ids': video_ids,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'total_reviews': total_reviews,
            'total_views': total_views,
            'average_views': average_views
        }
        
        # Add LLM judge scores if available
        if llm_scores:
            row['llm_relevance_score'] = llm_scores.get('relevance')
            row['llm_helpfulness_score'] = llm_scores.get('helpfulness')
            row['llm_conciseness_score'] = llm_scores.get('conciseness')
        
        # Insert the row into BigQuery
        table_id = PRODUCT_SUMMARIES_TABLE
        table = bigquery_client.get_table(table_id)
        
        errors = bigquery_client.insert_rows_json(table, [row])
        
        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
            return False
        
        logger.info(f"Successfully inserted product summary to BigQuery: {search_query}")
        return True
        
    except Exception as e:
        logger.error(f"Error inserting product summary to BigQuery: {e}")
        return False

def check_if_new_videos_available(search_query: str, existing_summary: Optional[Dict[str, Any]]) -> bool:
    """Check if there are new videos available for a search query that weren't in the previous summary"""
    try:
        # Get current video IDs for this query
        current_videos = get_video_summaries_by_query(search_query)
        current_video_ids = set(video['video_id'] for video in current_videos)
        
        if not existing_summary:
            # No existing summary, so any videos are "new"
            return len(current_video_ids) > 0
        
        # Get the video IDs that were used in the existing summary
        # We'll need to store this information in the summary or track it separately
        # For now, we'll assume if the number of videos has changed, there are new videos
        existing_video_count = existing_summary.get('total_reviews', 0)
        current_video_count = len(current_video_ids)
        
        if current_video_count > existing_video_count:
            logger.info(f"New videos detected for query '{search_query}': {existing_video_count} -> {current_video_count}")
            return True
        
        logger.info(f"No new videos detected for query '{search_query}': {current_video_count} videos (same as before)")
        return False
        
    except Exception as e:
        logger.error(f"Error checking for new videos for query {search_query}: {e}")
        return True  # Default to True to be safe

def should_generate_summary(search_query: str) -> tuple[bool, Optional[Dict[str, Any]], str]:
    """Determine if a summary should be generated and why"""
    try:
        # Check if summary already exists
        existing_summary = check_existing_product_summary(search_query)
        
        if not existing_summary:
            # No existing summary, should generate
            return True, None, "new_query"
        
        # Check if there are new videos
        has_new_videos = check_if_new_videos_available(search_query, existing_summary)
        
        if has_new_videos:
            return True, existing_summary, "new_videos"
        
        # No new videos, no need to generate
        return False, existing_summary, "no_changes"
        
    except Exception as e:
        logger.error(f"Error determining if summary should be generated for query {search_query}: {e}")
        return True, None, "error"

def get_all_search_queries_with_videos() -> List[str]:
    """Get all unique search queries that have video summaries"""
    try:
        query = f"""
        SELECT DISTINCT search_query
        FROM `{VIDEO_METADATA_TABLE}`
        WHERE summary_available = true 
        AND summary_content IS NOT NULL
        ORDER BY search_query
        """
        
        query_job = bigquery_client.query(query)
        results = list(query_job.result())
        
        search_queries = [row.search_query for row in results]
        logger.info(f"Found {len(search_queries)} search queries with video summaries")
        return search_queries
        
    except Exception as e:
        logger.error(f"Error getting search queries with videos: {e}")
        return []

def get_existing_summary_queries() -> List[str]:
    """Get all search queries that already have product summaries"""
    try:
        query = f"""
        SELECT DISTINCT search_query
        FROM `{PRODUCT_SUMMARIES_TABLE}`
        ORDER BY search_query
        """
        
        query_job = bigquery_client.query(query)
        results = list(query_job.result())
        
        existing_queries = [row.search_query for row in results]
        logger.info(f"Found {len(existing_queries)} existing product summaries")
        return existing_queries
        
    except Exception as e:
        logger.error(f"Error getting existing summary queries: {e}")
        return []

def auto_process_summaries() -> Dict[str, Any]:
    """Automatically process all search queries that need summaries"""
    try:
        logger.info("Starting automatic summary processing...")
        
        # Get all search queries with videos
        all_queries = get_all_search_queries_with_videos()
        if not all_queries:
            return {
                "status": "no_data",
                "message": "No search queries with video summaries found",
                "processed": 0,
                "skipped": 0,
                "errors": 0,
                "results": []
            }
        
        # Get existing summary queries
        existing_queries = get_existing_summary_queries()
        
        # Find queries that need processing
        queries_to_process = []
        for query in all_queries:
            if query not in existing_queries:
                queries_to_process.append((query, "new_query"))
            else:
                # Check if there are new videos
                should_generate, _, reason = should_generate_summary(query)
                if should_generate:
                    queries_to_process.append((query, reason))
        
        logger.info(f"Found {len(queries_to_process)} queries that need processing")
        
        # Process each query
        results = []
        processed = 0
        skipped = 0
        errors = 0
        
        for search_query, reason in queries_to_process:
            try:
                logger.info(f"Processing query: {search_query} (reason: {reason})")
                
                # Get video summaries for the query
                videos = get_video_summaries_by_query(search_query)
                
                if not videos or len(videos) < 2:
                    logger.warning(f"Skipping {search_query}: insufficient videos ({len(videos) if videos else 0})")
                    skipped += 1
                    results.append({
                        "search_query": search_query,
                        "status": "skipped",
                        "reason": f"insufficient_videos ({len(videos) if videos else 0})"
                    })
                    continue
                
                # Generate unified product summary
                unified_summary = generate_unified_product_summary(search_query, videos)
                
                if not unified_summary:
                    logger.error(f"Failed to generate summary for {search_query}")
                    errors += 1
                    results.append({
                        "search_query": search_query,
                        "status": "error",
                        "reason": "generation_failed"
                    })
                    continue
                
                # Extract product name
                product_name = extract_product_name(search_query)
                
                # Insert into BigQuery
                bigquery_success = insert_product_summary_to_bigquery(product_name, search_query, unified_summary['summary'], videos, unified_summary['llm_scores'])
                
                if not bigquery_success:
                    logger.error(f"Failed to save summary to BigQuery for {search_query}")
                    errors += 1
                    results.append({
                        "search_query": search_query,
                        "status": "error",
                        "reason": "bigquery_save_failed"
                    })
                    continue
                
                # Success
                processed += 1
                total_views = sum(video['view_count'] for video in videos)
                average_views = total_views / len(videos)
                
                results.append({
                    "search_query": search_query,
                    "status": "success",
                    "product_name": product_name,
                    "total_reviews": len(videos),
                    "total_views": total_views,
                    "average_views": average_views,
                    "reason": reason
                })
                
                logger.info(f"Successfully processed {search_query}")
                
            except Exception as e:
                logger.error(f"Error processing {search_query}: {e}")
                errors += 1
                results.append({
                    "search_query": search_query,
                    "status": "error",
                    "reason": str(e)
                })
        
        logger.info(f"Auto-processing complete: {processed} processed, {skipped} skipped, {errors} errors")
        
        return {
            "status": "completed",
            "message": f"Auto-processing complete: {processed} processed, {skipped} skipped, {errors} errors",
            "processed": processed,
            "skipped": skipped,
            "errors": errors,
            "total_queries": len(all_queries),
            "queries_to_process": len(queries_to_process),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in auto_process_summaries: {e}")
        return {
            "status": "error",
            "message": str(e),
            "processed": 0,
            "skipped": 0,
            "errors": 1,
            "results": []
        }

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy", 
        "service": "product-summary-api",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@app.route('/generate-summary', methods=['POST'])
def generate_product_summary():
    """Generate a unified product summary for a search query"""
    try:
        data = request.get_json()
        search_query = data.get('search_query')
        
        if not search_query:
            return jsonify({"error": "search_query is required"}), 400
        
        logger.info(f"Checking if summary should be generated for query: {search_query}")
        
        # Check if we should generate a summary
        should_generate, existing_summary, reason = should_generate_summary(search_query)
        
        if not should_generate:
            logger.info(f"No need to generate summary for query '{search_query}': {reason}")
            return jsonify({
                "status": "no_changes",
                "message": f"No new videos available for query: {search_query}",
                "data": existing_summary,
                "reason": reason
            })
        
        # Get video summaries for the query
        videos = get_video_summaries_by_query(search_query)
        
        if not videos:
            return jsonify({
                "error": f"No video summaries found for query: {search_query}"
            }), 404
        
        if len(videos) < 2:
            return jsonify({
                "error": f"Need at least 2 video summaries to generate unified summary. Found: {len(videos)}"
            }), 400
        
        # Generate unified product summary
        unified_summary = generate_unified_product_summary(search_query, videos)
        
        if not unified_summary:
            return jsonify({
                "error": "Failed to generate unified product summary"
            }), 500
        
        # Extract product name
        product_name = extract_product_name(search_query)
        
        # Insert into BigQuery (this will overwrite existing summary if reason is "new_videos")
        bigquery_success = insert_product_summary_to_bigquery(product_name, search_query, unified_summary['summary'], videos, unified_summary['llm_scores'])
        
        if not bigquery_success:
            return jsonify({
                "error": "Failed to save product summary to BigQuery"
            }), 500
        
        # Prepare response
        total_views = sum(video['view_count'] for video in videos)
        average_views = total_views / len(videos)
        
        response_data = {
            "product_name": product_name,
            "search_query": search_query,
            "summary_content": unified_summary['summary'],
            "total_reviews": len(videos),
            "total_views": total_views,
            "average_views": average_views,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Successfully generated product summary for: {search_query} (reason: {reason})")
        
        return jsonify({
            "status": "success",
            "message": f"Product summary generated successfully (reason: {reason})",
            "data": response_data,
            "reason": reason
        })
        
    except Exception as e:
        logger.error(f"Error in generate_product_summary: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/get-summary/<search_query>', methods=['GET'])
def get_product_summary(search_query):
    """Get existing product summary for a search query"""
    try:
        # URL decode the search query
        import urllib.parse
        decoded_query = urllib.parse.unquote(search_query)
        
        logger.info(f"Getting product summary for query: {decoded_query}")
        
        existing_summary = check_existing_product_summary(decoded_query)
        
        if not existing_summary:
            return jsonify({
                "error": f"No product summary found for query: {decoded_query}"
            }), 404
        
        return jsonify({
            "status": "success",
            "data": existing_summary
        })
        
    except Exception as e:
        logger.error(f"Error in get_product_summary: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/check-status/<search_query>', methods=['GET'])
def check_summary_status(search_query):
    """Check the status of a search query and whether it needs a summary generated"""
    try:
        # URL decode the search query
        import urllib.parse
        decoded_query = urllib.parse.unquote(search_query)
        
        logger.info(f"Checking status for query: {decoded_query}")
        
        # Check if we should generate a summary
        should_generate, existing_summary, reason = should_generate_summary(decoded_query)
        
        # Get current video count
        videos = get_video_summaries_by_query(decoded_query)
        current_video_count = len(videos)
        
        status_info = {
            "search_query": decoded_query,
            "should_generate": should_generate,
            "reason": reason,
            "current_video_count": current_video_count,
            "has_existing_summary": existing_summary is not None
        }
        
        if existing_summary:
            status_info["existing_summary"] = {
                "product_name": existing_summary.get('product_name'),
                "total_reviews": existing_summary.get('total_reviews'),
                "total_views": existing_summary.get('total_views'),
                "created_at": existing_summary.get('created_at')
            }
        
        if should_generate:
            status_info["message"] = f"Summary should be generated (reason: {reason})"
        else:
            status_info["message"] = f"No new videos available (reason: {reason})"
        
        return jsonify({
            "status": "success",
            "data": status_info
        })
        
    except Exception as e:
        logger.error(f"Error in check_summary_status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/auto-process', methods=['POST'])
def auto_process_endpoint():
    """Automatically process all search queries that need summaries"""
    try:
        logger.info("Auto-process endpoint called")
        
        # Get all search queries with videos
        query = f"""
        SELECT DISTINCT search_query
        FROM `{VIDEO_METADATA_TABLE}`
        WHERE summary_available = true 
        AND summary_content IS NOT NULL
        ORDER BY search_query
        """
        
        query_job = bigquery_client.query(query)
        all_queries = [row.search_query for row in query_job.result()]
        
        if not all_queries:
            return jsonify({
                "status": "no_data",
                "message": "No search queries with video summaries found"
            })
        
        # Get existing summary queries
        existing_query = f"""
        SELECT DISTINCT search_query
        FROM `{PRODUCT_SUMMARIES_TABLE}`
        ORDER BY search_query
        """
        
        existing_job = bigquery_client.query(existing_query)
        existing_queries = [row.search_query for row in existing_job.result()]
        
        # Find queries that need processing
        queries_to_process = []
        for query in all_queries:
            if query not in existing_queries:
                queries_to_process.append((query, "new_query"))
            else:
                # Check if there are new videos
                should_generate, _, reason = should_generate_summary(query)
                if should_generate:
                    queries_to_process.append((query, reason))
        
        logger.info(f"Found {len(queries_to_process)} queries that need processing")
        
        # Process each query
        results = []
        processed = 0
        
        for search_query, reason in queries_to_process:
            try:
                logger.info(f"Processing query: {search_query} (reason: {reason})")
                
                # Get video summaries for the query
                videos = get_video_summaries_by_query(search_query)
                
                if not videos or len(videos) < 2:
                    continue
                
                # Generate unified product summary
                unified_summary = generate_unified_product_summary(search_query, videos)
                
                if not unified_summary:
                    continue
                
                # Extract product name and save to BigQuery
                product_name = extract_product_name(search_query)
                bigquery_success = insert_product_summary_to_bigquery(product_name, search_query, unified_summary['summary'], videos, unified_summary['llm_scores'])
                
                if bigquery_success:
                    processed += 1
                    results.append({
                        "search_query": search_query,
                        "status": "success",
                        "reason": reason
                    })
                
            except Exception as e:
                logger.error(f"Error processing {search_query}: {e}")
        
        return jsonify({
            "status": "completed",
            "message": f"Auto-processing complete: {processed} processed",
            "total_queries": len(all_queries),
            "queries_to_process": len(queries_to_process),
            "processed": processed,
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Error in auto_process_endpoint: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 