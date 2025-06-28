from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict
import uuid
import time
from fastapi import HTTPException
from fastapi.background import BackgroundTasks
from fastapi import APIRouter

router = APIRouter()

class AutomationRequest(BaseModel):
    shoes: List[ShoeRequest] = Field(..., description="List of shoes to process")
    wait_minutes: int = Field(default=10, ge=1, le=60, description="Minutes to wait between search and summary generation")
    start_time: Optional[datetime] = Field(None, description="When to start the YouTube search (UTC ISO format)")

@app.post("/schedule", response_model=AutomationResponse)
async def schedule_automation(request: AutomationRequest, background_tasks: BackgroundTasks):
    try:
        # Validate request
        if not request.shoes:
            raise HTTPException(status_code=400, detail="At least one shoe must be specified")
        if request.start_time:
            now = datetime.now(timezone.utc)
            if request.start_time < now:
                raise HTTPException(status_code=400, detail="start_time cannot be in the past")
        # Generate job ID
        job_id = f"shoe_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        # Store job information
        jobs[job_id] = {
            'job_id': job_id,
            'status': 'scheduled',
            'state': 'scheduled',
            'shoes': [shoe.dict() for shoe in request.shoes],
            'wait_minutes': request.wait_minutes,
            'start_time': request.start_time.isoformat() if request.start_time else datetime.now(timezone.utc).isoformat(),
            'scheduled_time': datetime.now().isoformat()
        }
        # Start background task
        background_tasks.add_task(
            process_automation_job,
            job_id,
            [shoe.dict() for shoe in request.shoes],
            request.wait_minutes,
            request.start_time
        )
        return AutomationResponse(
            job_id=job_id,
            status='scheduled',
            message='Job scheduled successfully',
            scheduled_time=jobs[job_id]['scheduled_time'],
            shoes_count=len(request.shoes)
        )
    except Exception as e:
        logger.error(f"Error scheduling automation job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_automation_job(job_id: str, shoes: List[Dict], wait_minutes: int, start_time: Optional[datetime] = None):
    try:
        # Wait until start_time if provided
        if start_time:
            now = datetime.now(timezone.utc)
            delay = (start_time - now).total_seconds()
            if delay > 0:
                logger.info(f"Job {job_id}: Waiting {delay} seconds until start_time {start_time}")
                time.sleep(delay)
        # Update job status to running
        jobs[job_id]['status'] = 'running'
        jobs[job_id]['state'] = 'running'
        jobs[job_id]['start_date'] = datetime.now().isoformat()
        logger.info(f"Starting automation job {job_id} for {len(shoes)} shoes")
        // ... existing code ... 