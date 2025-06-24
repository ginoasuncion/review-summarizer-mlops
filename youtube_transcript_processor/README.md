# YouTube Transcript Processor

A Cloud Run service that automatically fetches transcripts for YouTube videos when new video metadata files are uploaded to Google Cloud Storage.

## Overview

This service monitors the `processed/videos/` folder in the YouTube processed data bucket and automatically fetches transcripts for new videos using the Oxylabs API. It saves the transcripts as text files and updates the video metadata with transcript information.

## Features

- **Automatic Detection**: Triggers when new video files are uploaded to `processed/videos/`
- **Transcript Fetching**: Uses Oxylabs API to fetch YouTube video transcripts
- **GCS Storage**: Saves transcripts as `.txt` files in `transcripts/` folder
- **Metadata Updates**: Updates video metadata with transcript file paths
- **Duplicate Prevention**: Skips videos that already have transcripts
- **Error Handling**: Robust error handling and logging

## Architecture

```
YouTube Search API → Data Processor → Transcript Processor
     ↓                    ↓                    ↓
Raw Data Bucket → Processed Data Bucket → Transcripts
```

## Configuration

### Environment Variables

- `SOURCE_BUCKET`: Source bucket containing processed video files (default: `youtube-processed-data-bucket`)
- `TRANSCRIPTS_BUCKET`: Bucket to store transcripts (default: `youtube-processed-data-bucket`)
- `OXYLABS_USERNAME`: Oxylabs API username
- `OXYLABS_PASSWORD`: Oxylabs API password

### Required Permissions

The service account needs:
- Storage Object Admin on the source and destination buckets
- Cloud Run Invoker for Pub/Sub push subscriptions

## Deployment

1. Set up Oxylabs credentials:
   ```bash
   gcloud run services update youtube-transcript-processor \
     --set-env-vars="OXYLABS_USERNAME=your_username,OXYLABS_PASSWORD=your_password" \
     --region=us-central1
   ```

2. Deploy the service:
   ```bash
   ./deploy.sh
   ```

## File Structure

```
youtube_transcript_processor/
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

1. **Trigger**: New file uploaded to `gs://youtube-processed-data-bucket/processed/videos/{video_id}.json`
2. **Processing**: Extract video ID and check if transcript exists
3. **Fetching**: Use Oxylabs API to get video transcript
4. **Saving**: Save transcript as `gs://youtube-processed-data-bucket/transcripts/{video_id}.txt`
5. **Updating**: Update video metadata with transcript information

## Output Format

### Transcript Files
- **Location**: `gs://youtube-processed-data-bucket/transcripts/{video_id}.txt`
- **Format**: Plain text with transcript content
- **Content**: Cleaned transcript text without timestamps or music markers

### Updated Video Metadata
```json
{
  "video_id": "abc123",
  "title": "Video Title",
  "transcript_available": true,
  "transcript_file": "gs://youtube-processed-data-bucket/transcripts/abc123.txt",
  "transcript_processed_at": "2025-06-24T22:00:00Z"
}
```

## Monitoring

Check logs:
```bash
gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=youtube-transcript-processor' --project=buoyant-yew-463209-k5
```

## Error Handling

- **No Transcript Available**: Logs warning and skips video
- **API Errors**: Logs error and continues with next video
- **Duplicate Transcripts**: Skips processing if transcript already exists
- **Invalid Files**: Skips non-video files in the monitored folder 