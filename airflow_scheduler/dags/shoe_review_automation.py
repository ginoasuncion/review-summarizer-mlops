"""
Shoe Review Automation DAG
Automates the process of searching YouTube for shoe reviews and generating product summaries
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
import requests
import time
import json
import logging
from typing import List, Dict, Any

# Default arguments for the DAG
default_args = {
    'owner': 'mlops-team',
    'depends_on_past': False,
    'start_date': datetime(2025, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# API endpoints
YOUTUBE_SEARCH_API = "https://youtube-search-api-nxbmt7mfiq-uc.a.run.app/search"
PRODUCT_SUMMARY_API = "https://product-summary-api-nxbmt7mfiq-uc.a.run.app/auto-process"

def search_youtube_for_shoe(shoe_name: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Search YouTube for reviews of a specific shoe
    """
    try:
        search_query = f"{shoe_name} review"
        
        payload = {
            "query": search_query,
            "max_results": max_results
        }
        
        logging.info(f"Searching YouTube for: {search_query}")
        
        response = requests.post(YOUTUBE_SEARCH_API, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        logging.info(f"YouTube search completed for {shoe_name}: {result.get('status')}")
        
        return {
            'shoe_name': shoe_name,
            'search_query': search_query,
            'status': result.get('status'),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Error searching YouTube for {shoe_name}: {e}")
        return {
            'shoe_name': shoe_name,
            'search_query': f"{shoe_name} review",
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def trigger_product_summary_generation() -> Dict[str, Any]:
    """
    Trigger the product summary generation process
    """
    try:
        logging.info("Triggering product summary generation")
        
        response = requests.post(PRODUCT_SUMMARY_API, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        logging.info(f"Product summary generation completed: {result}")
        
        return result
        
    except Exception as e:
        logging.error(f"Error triggering product summary generation: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def process_shoe_batch(**context) -> List[Dict[str, Any]]:
    """
    Process a batch of shoes - search YouTube for each shoe
    """
    # Get the list of shoes from the DAG run configuration
    shoes = context['dag_run'].conf.get('shoes', [])
    
    if not shoes:
        logging.warning("No shoes provided in DAG configuration")
        return []
    
    results = []
    for shoe in shoes:
        shoe_name = shoe.get('name', '')
        max_results = shoe.get('max_results', 5)
        
        if shoe_name:
            result = search_youtube_for_shoe(shoe_name, max_results)
            results.append(result)
            
            # Small delay between requests to avoid overwhelming the API
            time.sleep(2)
    
    logging.info(f"Processed {len(results)} shoes")
    return results

def wait_for_processing(**context) -> None:
    """
    Wait for the YouTube search processing to complete
    """
    wait_minutes = context['dag_run'].conf.get('wait_minutes', 10)
    logging.info(f"Waiting {wait_minutes} minutes for processing to complete")
    time.sleep(wait_minutes * 60)

# Create the DAG
dag = DAG(
    'shoe_review_automation',
    default_args=default_args,
    description='Automate shoe review processing pipeline',
    schedule_interval=None,  # Manual triggers only
    catchup=False,
    tags=['mlops', 'shoe-reviews', 'automation'],
)

# Task 1: Search YouTube for all shoes in the batch
search_youtube_task = PythonOperator(
    task_id='search_youtube_for_shoes',
    python_callable=process_shoe_batch,
    provide_context=True,
    dag=dag,
)

# Task 2: Wait for processing to complete
wait_task = PythonOperator(
    task_id='wait_for_processing',
    python_callable=wait_for_processing,
    provide_context=True,
    dag=dag,
)

# Task 3: Trigger product summary generation
generate_summaries_task = PythonOperator(
    task_id='generate_product_summaries',
    python_callable=trigger_product_summary_generation,
    dag=dag,
)

# Task 4: Log completion
log_completion_task = BashOperator(
    task_id='log_completion',
    bash_command='echo "Shoe review automation completed successfully"',
    dag=dag,
)

# Define task dependencies
search_youtube_task >> wait_task >> generate_summaries_task >> log_completion_task 