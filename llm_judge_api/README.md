# LLM Judge API

A standalone Cloud Run service for evaluating summaries using an LLM judge.

## Features

- Evaluates summaries based on relevance, helpfulness, and conciseness
- Handles rate limits with exponential backoff and retry logic
- Centralized LLM judge service for multiple applications
- RESTful API interface

## API Endpoints

### POST /evaluate

Evaluates a summary using the LLM judge.

**Request Body:**
```json
{
  "summary_content": "The summary text to evaluate",
  "search_query": "The original search query",
  "video_title": "Optional video title",
  "openai_model": "gpt-4o",
  "max_retries": 3
}
```

**Response:**
```json
{
  "success": true,
  "scores": {
    "relevance": 0.85,
    "helpfulness": 0.92,
    "conciseness": 0.78
  }
}
```

### GET /health

Health check endpoint.

## Deployment

```bash
chmod +x deploy.sh
./deploy.sh
```

## Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key
- `PORT`: Port to run the service on (default: 8080) 