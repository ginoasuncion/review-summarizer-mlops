#!/bin/bash

# YouTube Pipeline Cleanup Script
# This script clears all files from the YouTube pipeline buckets and BigQuery tables

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="buoyant-yew-463209-k5"
DATASET_ID="youtube_reviews"
SEARCH_BUCKET="youtube-search-data-bucket"
PROCESSED_BUCKET="youtube-processed-data-bucket"

echo -e "${YELLOW}🧹 YouTube Pipeline Cleanup Script${NC}"
echo "============================================="

# Function to confirm deletion
confirm_deletion() {
    local resource_type=$1
    echo -e "${RED}⚠️  WARNING: This will delete ALL ${resource_type}${NC}"
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${YELLOW}❌ Operation cancelled${NC}"
        exit 1
    fi
}

# Function to clear bucket
clear_bucket() {
    local bucket_name=$1
    echo -e "${YELLOW}🗑️  Clearing bucket: ${bucket_name}${NC}"
    
    # Check if bucket has files
    file_count=$(gsutil ls -r "gs://${bucket_name}/" 2>/dev/null | wc -l || echo "0")
    if [ "$file_count" -eq 0 ]; then
        echo "Bucket is already empty"
        return
    fi
    
    # List files before deletion
    echo "Files to be deleted:"
    gsutil ls -r "gs://${bucket_name}/" | head -10
    
    # Delete all files
    gsutil -m rm -r "gs://${bucket_name}/**"
    echo -e "${GREEN}✅ Successfully cleared bucket: ${bucket_name}${NC}"
}

# Function to clear BigQuery tables
clear_bigquery_tables() {
    echo -e "${BLUE}🗄️  Clearing BigQuery tables in dataset: ${DATASET_ID}${NC}"
    
    # List existing tables
    echo "Existing tables:"
    bq ls --project_id="${PROJECT_ID}" "${DATASET_ID}" 2>/dev/null || {
        echo "Dataset ${DATASET_ID} does not exist or is empty"
        return
    }
    
    # Define known table names
    known_tables=("product_summaries" "video_metadata")
    
    # Check and delete each known table
    for table_id in "${known_tables[@]}"; do
        if bq show --project_id="${PROJECT_ID}" "${DATASET_ID}.${table_id}" >/dev/null 2>&1; then
            echo "Deleting table: ${table_id}"
            bq rm --project_id="${PROJECT_ID}" --force "${DATASET_ID}.${table_id}"
        else
            echo "Table ${table_id} does not exist, skipping..."
        fi
    done
    
    echo -e "${GREEN}✅ Successfully cleared BigQuery tables${NC}"
}

# Function to check if BigQuery dataset exists
check_bigquery_dataset() {
    bq show --project_id="${PROJECT_ID}" "${DATASET_ID}" >/dev/null 2>&1
    return $?
}

# Main execution
echo "This script will clear the following resources:"
echo "  - ${SEARCH_BUCKET} (raw search data)"
echo "  - ${PROCESSED_BUCKET} (processed videos, transcripts, summaries)"
if check_bigquery_dataset; then
    echo "  - BigQuery dataset: ${DATASET_ID} (product summaries and video metadata)"
else
    echo "  - BigQuery dataset: ${DATASET_ID} (does not exist)"
fi
echo ""

# Confirm before proceeding
confirm_deletion "resources"

# Clear search bucket
echo ""
echo "Clearing search data bucket..."
clear_bucket "${SEARCH_BUCKET}"

# Clear processed bucket
echo ""
echo "Clearing processed data bucket..."
clear_bucket "${PROCESSED_BUCKET}"

# Clear BigQuery tables
echo ""
if check_bigquery_dataset; then
    echo "Clearing BigQuery tables..."
    clear_bigquery_tables
else
    echo "BigQuery dataset ${DATASET_ID} does not exist, skipping..."
fi

echo ""
echo -e "${GREEN}🎉 All resources cleared successfully!${NC}"
echo ""
echo "Next steps:"
echo "  1. Run a new search to test the pipeline"
echo "  2. Monitor the processing flow"
echo "  3. Check that search queries are extracted correctly"
echo "  4. Verify data flows through all stages" 