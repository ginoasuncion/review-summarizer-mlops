import json
import os
import logging
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from flask import Flask, request, jsonify
from google.cloud import storage
from google.cloud import bigquery
from google.cloud.exceptions import NotFound

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize clients
storage_client = storage.Client()
bigquery_client = bigquery.Client()

# Configuration
PROJECT_ID = os.environ.get('GCP_PROJECT_ID', 'buoyant-yew-463209-k5')
BIGQUERY_DATASET = os.environ.get('BIGQUERY_DATASET', 'youtube_reviews')
BIGQUERY_PROJECT = os.environ.get('BIGQUERY_PROJECT', PROJECT_ID)
PRODUCT_SUMMARIES_TABLE = f"{BIGQUERY_PROJECT}.{BIGQUERY_DATASET}.product_summaries"
QUERY_LOGS_BUCKET = os.environ.get('QUERY_LOGS_BUCKET', 'youtube-processed-data-bucket')

# Flask app
app = Flask(__name__)

def normalize_product_name(product_name: str) -> str:
    """Normalize product name for comparison"""
    if not product_name:
        return ""
    # Remove common variations and normalize
    normalized = product_name.lower().strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized

def search_bigquery_for_product(product_name: str) -> Optional[Dict[str, Any]]:
    """Search BigQuery for existing product summary"""
    try:
        normalized_product = normalize_product_name(product_name)
        
        # Query BigQuery for the product
        query = f"""
        SELECT product_name, search_query, summary_content, total_reviews, 
               total_views, average_views, processed_at
        FROM `{PRODUCT_SUMMARIES_TABLE}`
        WHERE LOWER(product_name) LIKE '%{normalized_product}%'
           OR LOWER(search_query) LIKE '%{normalized_product}%'
        ORDER BY processed_at DESC
        LIMIT 1
        """
        
        query_job = bigquery_client.query(query)
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
                'processed_at': row.processed_at.isoformat() if row.processed_at else None,
                'found_in_bigquery': True
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Error searching BigQuery for product {product_name}: {e}")
        return None

def log_query_to_gcs(product_name: str, found: bool, summary_data: Optional[Dict[str, Any]] = None):
    """Log query results to Cloud Storage"""
    try:
        bucket = storage_client.bucket(QUERY_LOGS_BUCKET)
        
        # Create log entry
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'product_name': product_name,
            'found_in_bigquery': found,
            'user_ip': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
            'request_id': request.headers.get('X-Request-ID', ''),
            'status': 'success' if found else 'not_found'
        }
        
        if summary_data:
            log_entry['summary_data'] = {
                'product_name': summary_data.get('product_name'),
                'total_reviews': summary_data.get('total_reviews'),
                'processed_at': summary_data.get('processed_at')
            }
        
        # Create filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        safe_product_name = re.sub(r'[^a-zA-Z0-9]', '_', product_name)
        filename = f"query_logs/{timestamp}_{safe_product_name}_{'found' if found else 'not_found'}.json"
        
        # Upload to GCS
        blob = bucket.blob(filename)
        blob.upload_from_string(
            json.dumps(log_entry, indent=2),
            content_type='application/json'
        )
        
        logger.info(f"Logged query for {product_name} to {filename}")
        
    except Exception as e:
        logger.error(f"Error logging query to GCS: {e}")

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'service': 'product-query-api',
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'bigquery_table': PRODUCT_SUMMARIES_TABLE,
        'version': 'mvp'
    })

@app.route('/query', methods=['POST'])
def query_product():
    """Query product summary from BigQuery and log the result"""
    try:
        # Get request data
        data = request.get_json()
        
        if not data or 'product_name' not in data:
            return jsonify({
                'error': 'product_name is required',
                'example': {
                    'product_name': 'Adidas Ultraboost'
                }
            }), 400
        
        product_name = data.get('product_name', '').strip()
        
        if not product_name:
            return jsonify({'error': 'product_name cannot be empty'}), 400
        
        logger.info(f"Querying product: {product_name}")
        
        # Search BigQuery for existing summary
        summary_data = search_bigquery_for_product(product_name)
        
        if summary_data:
            # Product found in BigQuery
            logger.info(f"Product {product_name} found in BigQuery")
            log_query_to_gcs(product_name, True, summary_data)
            
            return jsonify({
                'status': 'found',
                'message': f'Product summary found for "{product_name}"',
                'data': summary_data,
                'source': 'bigquery'
            })
        
        else:
            # Product not found in BigQuery
            logger.info(f"Product {product_name} not found in BigQuery")
            log_query_to_gcs(product_name, False)
            
            return jsonify({
                'status': 'not_found',
                'message': f'Product "{product_name}" not found in database.',
                'note': 'Query has been logged. Pipeline triggering not available in MVP version.'
            })
    
    except Exception as e:
        logger.error(f"Error in query_product: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/search', methods=['GET'])
def search_products():
    """Search for products in BigQuery with partial matching"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({
                'error': 'Query parameter "q" is required',
                'example': '/search?q=adidas'
            }), 400
        
        if len(query) < 2:
            return jsonify({
                'error': 'Query must be at least 2 characters long'
            }), 400
        
        # Search BigQuery for products
        search_query = f"""
        SELECT product_name, search_query, summary_content, total_reviews, 
               total_views, average_views, processed_at
        FROM `{PRODUCT_SUMMARIES_TABLE}`
        WHERE LOWER(product_name) LIKE '%{query.lower()}%'
           OR LOWER(search_query) LIKE '%{query.lower()}%'
        ORDER BY processed_at DESC
        LIMIT 10
        """
        
        query_job = bigquery_client.query(search_query)
        results = list(query_job.result())
        
        products = []
        for row in results:
            products.append({
                'product_name': row.product_name,
                'search_query': row.search_query,
                'summary_content': row.summary_content[:500] + '...' if len(row.summary_content) > 500 else row.summary_content,
                'total_reviews': row.total_reviews,
                'total_views': row.total_views,
                'average_views': row.average_views,
                'processed_at': row.processed_at.isoformat() if row.processed_at else None
            })
        
        return jsonify({
            'query': query,
            'total_results': len(products),
            'products': products
        })
        
    except Exception as e:
        logger.error(f"Error in search_products: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get statistics about stored products"""
    try:
        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM `{PRODUCT_SUMMARIES_TABLE}`"
        count_job = bigquery_client.query(count_query)
        total_count = list(count_job.result())[0].total
        
        # Get recent products
        recent_query = f"""
        SELECT product_name, processed_at, total_reviews
        FROM `{PRODUCT_SUMMARIES_TABLE}`
        ORDER BY processed_at DESC
        LIMIT 5
        """
        recent_job = bigquery_client.query(recent_query)
        recent_products = []
        for row in recent_job.result():
            recent_products.append({
                'product_name': row.product_name,
                'processed_at': row.processed_at.isoformat() if row.processed_at else None,
                'total_reviews': row.total_reviews
            })
        
        return jsonify({
            'total_products': total_count,
            'recent_products': recent_products,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in get_stats: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/logs', methods=['GET'])
def get_query_logs():
    """Get query logs from Cloud Storage"""
    try:
        # Get query parameters
        limit = request.args.get('limit', 10, type=int)
        status = request.args.get('status', '')  # 'found', 'not_found', or empty for all
        
        if limit > 50:
            limit = 50  # Cap at 50 logs per request
        
        bucket = storage_client.bucket(QUERY_LOGS_BUCKET)
        
        # List all log files
        blobs = bucket.list_blobs(prefix='query_logs/')
        
        logs = []
        for blob in blobs:
            if blob.name.endswith('.json'):
                try:
                    content = blob.download_as_text()
                    log_entry = json.loads(content)
                    
                    # Filter by status if specified
                    if status and log_entry.get('status') != status:
                        continue
                    
                    # Add filename to log entry
                    log_entry['filename'] = blob.name
                    
                    logs.append(log_entry)
                        
                except Exception as e:
                    logger.warning(f"Error reading log file {blob.name}: {e}")
                    continue
        
        # Sort by timestamp (newest first) and limit results
        logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        logs = logs[:limit]
        
        return jsonify({
            'total_logs': len(logs),
            'requested_limit': limit,
            'status_filter': status if status else 'all',
            'logs': logs
        })
        
    except Exception as e:
        logger.error(f"Error getting query logs: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@app.route('/logs/stats', methods=['GET'])
def get_log_stats():
    """Get statistics about query logs"""
    try:
        bucket = storage_client.bucket(QUERY_LOGS_BUCKET)
        
        # List all log files
        blobs = bucket.list_blobs(prefix='query_logs/')
        
        total_logs = 0
        found_count = 0
        not_found_count = 0
        product_counts = {}
        
        for blob in blobs:
            if blob.name.endswith('.json'):
                try:
                    content = blob.download_as_text()
                    log_entry = json.loads(content)
                    
                    total_logs += 1
                    status = log_entry.get('status', 'unknown')
                    
                    if status == 'success':
                        found_count += 1
                    elif status == 'not_found':
                        not_found_count += 1
                    
                    # Count by product
                    product_name = log_entry.get('product_name', 'unknown')
                    product_counts[product_name] = product_counts.get(product_name, 0) + 1
                        
                except Exception as e:
                    logger.warning(f"Error reading log file {blob.name}: {e}")
                    continue
        
        # Get top 5 most queried products
        top_products = sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return jsonify({
            'total_queries': total_logs,
            'found_count': found_count,
            'not_found_count': not_found_count,
            'success_rate': (found_count / total_logs * 100) if total_logs > 0 else 0,
            'top_queried_products': [{'product': p[0], 'count': p[1]} for p in top_products],
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    # Run the Flask app
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False) 