#!/bin/bash

# Script to update existing BigQuery tables with LLM judge score columns

set -e

PROJECT_ID="buoyant-yew-463209-k5"
DATASET_ID="youtube_reviews"

echo "🔄 Updating BigQuery table schemas with LLM judge scores..."

# Update product_summaries table
echo "📊 Adding LLM judge scores to product_summaries table..."
bq query --use_legacy_sql=false --project_id=$PROJECT_ID "
ALTER TABLE \`$PROJECT_ID.$DATASET_ID.product_summaries\`
ADD COLUMN llm_relevance_score FLOAT64,
ADD COLUMN llm_helpfulness_score FLOAT64,
ADD COLUMN llm_conciseness_score FLOAT64;
" || echo "Columns may already exist in product_summaries table"

# Update video_metadata table
echo "📊 Adding LLM judge scores to video_metadata table..."
bq query --use_legacy_sql=false --project_id=$PROJECT_ID "
ALTER TABLE \`$PROJECT_ID.$DATASET_ID.video_metadata\`
ADD COLUMN llm_relevance_score FLOAT64,
ADD COLUMN llm_helpfulness_score FLOAT64,
ADD COLUMN llm_conciseness_score FLOAT64;
" || echo "Columns may already exist in video_metadata table"

echo "✅ BigQuery table schemas updated successfully!"
echo ""
echo "📋 Summary of changes:"
echo "   - Added llm_relevance_score (FLOAT64) to both tables"
echo "   - Added llm_helpfulness_score (FLOAT64) to both tables"
echo "   - Added llm_conciseness_score (FLOAT64) to both tables"
echo ""
echo "🔧 Next steps:"
echo "   1. Deploy the updated services with LLM judge integration"
echo "   2. Test the new functionality with existing or new summaries"
echo "   3. Monitor the scores in BigQuery to ensure they're being populated correctly" 