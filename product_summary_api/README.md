# 🚀 Review Summarizer MLOps

An automated system that retrieves and summarizes product reviews or video transcripts using LLMs — built with FastAPI and MLOps best practices.

---

## 🛠 Installation

### 1. Clone the repository

```bash
git clone https://github.com/ginoasuncion/review-summarizer-mlops.git
cd review-summarizer-mlops
```

### 2. Set up virtual environment using [uv](https://github.com/astral-sh/uv)

```bash
uv venv
source .venv/bin/activate  # or .uv/bin/activate if that's your setup
```

### 3. Install dependencies

```bash
uv pip install --system .
```

---

## 🧪 Running Tests

To run all tests:

```bash
pytest
```

You can also check type correctness:

```bash
mypy .
```

---

## ✅ Developer Setup

### Install and enable pre-commit hooks

```bash
uv pip install pre-commit
pre-commit install
```

### Run manually

```bash
black .
ruff check . --fix
pytest
mypy .
```

---

## 🔁 GitHub Actions

CI automatically checks:
- ✅ Formatting via **Black**
- ✅ Linting via **Ruff**
- ✅ Tests via **Pytest**
- ✅ Type checking via **Mypy**

---

## 🧠 GitHub Issue Automation

This project uses a GitHub Actions workflow to **automatically create a new branch** when an issue is opened.

- Branches follow this format:

  ```
  issue-<number>-<slugified-title>
  ```

  Example:  
  `issue-7-add-openai-summarizer-module`

- ✅ Requires a secret named `GH_PAT` with `repo` and `workflow` scopes.

---

## 📂 Project Structure

```
├── main.py                    # FastAPI app entry point
├── tests/                     # Pytest-based tests
├── youtube_search_api/        # YouTube Search API (Cloud Run)
│   ├── main.py               # FastAPI application
│   ├── requirements.txt      # Dependencies
│   ├── Dockerfile           # Container configuration
│   ├── cloudbuild.yaml      # Cloud Build config
│   ├── deploy.sh            # Deployment script
│   ├── setup.sh             # Setup script
│   ├── test_api.py          # API tests
│   └── README.md            # API documentation
├── pyproject.toml            # Project config and dependencies
├── requirements.txt
└── README.md
```

---

## 🎥 YouTube Search API

The project includes a **YouTube Search API** component that:

- 🔍 Searches YouTube videos using Oxylabs API
- ☁️ Stores results in Google Cloud Storage
- 🚀 Deployed on Google Cloud Run
- 📊 Provides structured JSON responses

### Quick Start

```bash
cd youtube_search_api
./setup.sh
```

### Features

- **FastAPI-based REST API**
- **Oxylabs integration** for YouTube search
- **Google Cloud Storage** for data persistence
- **Cloud Run deployment** with auto-scaling
- **Comprehensive testing** and monitoring
- **Docker containerization**

### Deployment

```bash
# Deploy to Cloud Run
./deploy.sh

# Or use Cloud Build
gcloud builds submit --config cloudbuild.yaml .
```

For detailed documentation, see [`youtube_search_api/README.md`](youtube_search_api/README.md).

---

## 📦 Download

[![Download](https://img.shields.io/badge/Download-ZIP-blue?logo=github)](https://github.com/ginoasuncion/review-summarizer-mlops/archive/refs/heads/main.zip)

# Product Summary API

A Cloud Run service that generates unified product summaries from multiple YouTube video reviews stored in BigQuery.

## Overview

This service takes a search query, retrieves all video summaries for that query from the `video_metadata` BigQuery table, concatenates them, and generates a comprehensive unified product summary using ChatGPT. The result is stored in the `product_summaries` BigQuery table.

## Features

- **Query-based Processing**: Takes a search query and finds all related video summaries
- **Unified Summarization**: Uses ChatGPT to create comprehensive product summaries from multiple reviews
- **BigQuery Integration**: Reads from `video_metadata` table and writes to `product_summaries` table
- **Duplicate Prevention**: Checks for existing summaries before generating new ones
- **Structured Output**: Provides detailed product insights including pros/cons, features, and recommendations

## API Endpoints

### Health Check
```
GET /health
```
Returns service health status.

### Generate Product Summary
```
POST /generate-summary
Content-Type: application/json

{
  "search_query": "Adidas Ultraboost review"
}
```

Generates a unified product summary for the given search query.

**Response:**
```json
{
  "status": "success",
  "message": "Product summary generated successfully",
  "data": {
    "product_name": "Adidas Ultraboost",
    "search_query": "Adidas Ultraboost review",
    "summary_content": "...",
    "total_reviews": 5,
    "total_views": 1500000,
    "average_views": 300000,
    "processed_at": "2024-01-01T12:00:00Z"
  }
}
```

### Get Existing Summary
```
GET /get-summary/{search_query}
```

Retrieves an existing product summary for the given search query.

## Environment Variables

- `GCP_PROJECT_ID`: Google Cloud Project ID
- `BIGQUERY_DATASET`: BigQuery dataset name (default: youtube_reviews)
- `BIGQUERY_PROJECT`: BigQuery project ID
- `OPENAI_API_KEY`: OpenAI API key for ChatGPT integration
- `OPENAI_MODEL`: OpenAI model to use (default: gpt-3.5-turbo)

## Deployment

1. Set the OpenAI API key:
```bash
gcloud run services update product-summary-api \
  --region us-central1 \
  --project buoyant-yew-463209-k5 \
  --set-env-vars OPENAI_API_KEY=your_openai_api_key_here
```

2. Deploy the service:
```bash
./deploy.sh
```

## Usage Examples

### Generate a product summary
```bash
curl -X POST https://product-summary-api-xxxxx-uc.a.run.app/generate-summary \
  -H 'Content-Type: application/json' \
  -d '{"search_query": "Nike Air Force 1 review"}'
```

### Get an existing summary
```bash
curl -X GET "https://product-summary-api-xxxxx-uc.a.run.app/get-summary/Nike%20Air%20Force%201%20review"
```

## BigQuery Schema

The service writes to the `product_summaries` table with the following schema:
- `product_name`: Extracted product name
- `search_query`: Original search query
- `summary_content`: Generated unified summary
- `total_reviews`: Number of videos processed
- `total_views`: Total view count across all videos
- `average_views`: Average view count per video
- `processed_at`: Timestamp of processing
- `summary_file`: GCS file path (placeholder)
- `processing_strategy`: Processing method used

## Requirements

- At least 2 video summaries must exist for the search query
- OpenAI API key must be configured
- BigQuery tables must exist and be accessible
