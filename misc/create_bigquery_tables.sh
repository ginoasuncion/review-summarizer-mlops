#!/bin/bash

# Script to create BigQuery dataset and tables for YouTube Review Summarizer pipeline

set -e

PROJECT_ID="buoyant-yew-463209-k5"
DATASET_ID="youtube_reviews"
LOCATION="US"

# Table names
PRODUCT_SUMMARIES="product_summaries"
VIDEO_METADATA="video_metadata"

# Create dataset if it doesn't exist
bq --location=${LOCATION} mk --dataset --description "YouTube product review summaries and video metadata" ${PROJECT_ID}:${DATASET_ID} || echo "Dataset already exists."

echo "Creating table: ${PRODUCT_SUMMARIES}"
bq mk --table --project_id=${PROJECT_ID} ${DATASET_ID}.${PRODUCT_SUMMARIES} \
product_name:STRING,\
search_query:STRING,\
summary_content:STRING,\
total_reviews:INTEGER,\
total_views:INTEGER,\
average_views:FLOAT,\
processed_at:TIMESTAMP,\
summary_file:STRING,\
processing_strategy:STRING,\
llm_relevance_score:FLOAT,\
llm_helpfulness_score:FLOAT,\
llm_conciseness_score:FLOAT || echo "Table ${PRODUCT_SUMMARIES} already exists."

echo "Creating table: ${VIDEO_METADATA}"
bq mk --table --project_id=${PROJECT_ID} ${DATASET_ID}.${VIDEO_METADATA} \
video_id:STRING,\
title:STRING,\
channel_name:STRING,\
view_count:INTEGER,\
duration:STRING,\
url:STRING,\
search_query:STRING,\
transcript_available:BOOLEAN,\
summary_available:BOOLEAN,\
transcript_file:STRING,\
summary_file:STRING,\
processed_at:TIMESTAMP,\
summary_content:STRING,\
summary_processed_at:TIMESTAMP,\
llm_relevance_score:FLOAT,\
llm_helpfulness_score:FLOAT,\
llm_conciseness_score:FLOAT || echo "Table ${VIDEO_METADATA} already exists."

echo "✅ BigQuery dataset and tables are ready!" 