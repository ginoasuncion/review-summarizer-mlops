#!/usr/bin/env python3
"""
Test script for the Airflow Scheduler API
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "https://airflow-scheduler-nxbmt7mfiq-uc.a.run.app"

def test_health():
    """Test the health endpoint"""
    print("🔍 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_schedule_automation():
    """Test scheduling an automation job"""
    print("\n🚀 Testing schedule automation...")
    
    payload = {
        "shoes": [
            {
                "name": "Nike Air Jordan 1",
                "max_results": 3
            },
            {
                "name": "Adidas Ultraboost",
                "max_results": 2
            }
        ],
        "wait_minutes": 5
    }
    
    try:
        response = requests.post(f"{BASE_URL}/schedule", json=payload)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Job scheduled successfully!")
            print(f"Job ID: {result['job_id']}")
            print(f"Message: {result['message']}")
            return result['job_id']
        else:
            print(f"❌ Failed to schedule job: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Schedule automation failed: {e}")
        return None

def test_get_job_status(job_id):
    """Test getting job status"""
    print(f"\n📊 Testing job status for {job_id}...")
    
    try:
        response = requests.get(f"{BASE_URL}/jobs/{job_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Job Status: {result['status']}")
            print(f"State: {result['state']}")
            print(f"Start Date: {result['start_date']}")
            print(f"End Date: {result['end_date']}")
            return result['state']
        else:
            print(f"❌ Failed to get job status: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Get job status failed: {e}")
        return None

def test_list_jobs():
    """Test listing jobs"""
    print("\n📋 Testing list jobs...")
    
    try:
        response = requests.get(f"{BASE_URL}/jobs?limit=5")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Total jobs: {result['total']}")
            for job in result['jobs']:
                print(f"  - {job['job_id']}: {job['status']}")
        else:
            print(f"❌ Failed to list jobs: {response.text}")
            
    except Exception as e:
        print(f"❌ List jobs failed: {e}")

def monitor_job(job_id, max_wait=300):
    """Monitor a job until completion or timeout"""
    print(f"\n⏳ Monitoring job {job_id}...")
    
    start_time = time.time()
    while time.time() - start_time < max_wait:
        status = test_get_job_status(job_id)
        
        if status in ['success', 'failed']:
            print(f"✅ Job completed with status: {status}")
            return status
        elif status == 'running':
            print("⏳ Job is still running, waiting 30 seconds...")
            time.sleep(30)
        else:
            print(f"❓ Unknown status: {status}")
            time.sleep(30)
    
    print(f"⏰ Timeout reached after {max_wait} seconds")
    return None

def main():
    """Run all tests"""
    print("🧪 Starting Airflow Scheduler API Tests")
    print("=" * 50)
    
    # Test health
    if not test_health():
        print("❌ Health check failed, stopping tests")
        return
    
    # Test list jobs (before scheduling)
    test_list_jobs()
    
    # Test schedule automation
    job_id = test_schedule_automation()
    if not job_id:
        print("❌ Failed to schedule job, stopping tests")
        return
    
    # Wait a moment for job to start
    time.sleep(5)
    
    # Test get job status
    test_get_job_status(job_id)
    
    # Monitor job (optional - uncomment to monitor)
    # monitor_job(job_id, max_wait=600)  # 10 minutes max
    
    # Test list jobs (after scheduling)
    test_list_jobs()
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    main() 