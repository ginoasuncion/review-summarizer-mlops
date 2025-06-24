# YouTube Transcript Summarizer

A Cloud Run service that automatically generates summaries of YouTube video transcripts using ChatGPT when new transcript files are uploaded to Google Cloud Storage.

## Overview

This service monitors the `transcripts/` folder in the YouTube processed data bucket and automatically generates AI-powered summaries for new transcript files using OpenAI's ChatGPT API. It saves the summaries as text files and updates the video metadata with summary information.

## Features

- **Automatic Detection**: Triggers when new transcript files are uploaded to `transcripts/`
- **ChatGPT Integration**: Uses OpenAI's GPT-3.5-turbo to generate intelligent summaries
- **Structured Summaries**: Creates comprehensive summaries with key points, recommendations, and ratings
- **GCS Storage**: Saves summaries as `.txt` files in `summaries/` folder
- **Metadata Updates**: Updates video metadata with summary file paths
- **Duplicate Prevention**: Skips videos that already have summaries
- **Error Handling**: Robust error handling and logging

## Architecture

```
YouTube Search API → Data Processor → Transcript Processor → Transcript Summarizer
     ↓                    ↓                    ↓                    ↓
Raw Data Bucket → Processed Data Bucket → Transcripts → Summaries
```

## Configuration

### Environment Variables

- `SOURCE_BUCKET`: Source bucket containing transcript files (default: `youtube-processed-data-bucket`)
- `SUMMARIES_BUCKET`: Bucket to store summaries (default: `youtube-processed-data-bucket`)
- `OPENAI_API_KEY`: OpenAI API key for ChatGPT access
- `OPENAI_MODEL`: OpenAI model to use (default: `gpt-3.5-turbo`)

### Required Permissions

The service account needs:
- Storage Object Admin on the source and destination buckets
- Cloud Run Invoker for Pub/Sub push subscriptions

## Deployment

1. Set up OpenAI API key:
   ```bash
   gcloud run services update youtube-transcript-summarizer \
     --set-env-vars="OPENAI_API_KEY=your_openai_api_key" \
     --region=us-central1
   ```

2. Deploy the service:
   ```bash
   ./deploy.sh
   ```

## File Structure

```
youtube_transcript_summarizer/
├── main.py              # Main application code
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── deploy.sh           # Deployment script
└── README.md           # This file
```

## API Endpoints

- `GET /health`: Health check endpoint
- `POST /process`: Webhook endpoint for Cloud Storage events

## Data Flow

1. **Trigger**: New file uploaded to `gs://youtube-processed-data-bucket/transcripts/{video_id}.txt`
2. **Processing**: Extract video ID and check if summary exists
3. **Content Retrieval**: Get transcript content and video metadata
4. **Summary Generation**: Use ChatGPT to generate structured summary
5. **Saving**: Save summary as `gs://youtube-processed-data-bucket/summaries/{video_id}.txt`
6. **Updating**: Update video metadata with summary information

## Summary Format

The ChatGPT-generated summaries include:

1. **Main Topic**: What the video is about
2. **Key Points**: Main points discussed
3. **Product Review Details**: Products reviewed and findings (if applicable)
4. **Recommendations**: Recommendations or conclusions made
5. **Overall Rating/Opinion**: Overall sentiment or rating

## Output Format

### Summary Files
- **Location**: `gs://youtube-processed-data-bucket/summaries/{video_id}.txt`
- **Format**: Structured text with bullet points and sections
- **Content**: AI-generated comprehensive summary

### Updated Video Metadata
```json
{
  "video_id": "abc123",
  "title": "Video Title",
  "summary_available": true,
  "summary_file": "gs://youtube-processed-data-bucket/summaries/abc123.txt",
  "summary_processed_at": "2025-06-24T22:00:00Z"
}
```

## Monitoring

Check logs:
```bash
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=youtube-transcript-summarizer' --project=buoyant-yew-463209-k5
```

## Error Handling

- **No Transcript Available**: Logs warning and skips video
- **API Errors**: Logs error and continues with next video
- **Duplicate Summaries**: Skips processing if summary already exists
- **Invalid Files**: Skips non-transcript files in the monitored folder
- **OpenAI API Issues**: Handles rate limits and API errors gracefully

## Cost Considerations

- **OpenAI API**: Each summary generation costs approximately $0.002-0.005
- **Cloud Run**: Pay per request and compute time
- **Storage**: Minimal cost for storing summary files 