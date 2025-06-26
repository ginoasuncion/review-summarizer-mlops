#!/usr/bin/env python3
"""
Test script for YouTube Search API
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")

def test_health_check():
    """Test the health check endpoint."""
    print("🏥 Testing health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def test_detailed_health():
    """Test the detailed health check endpoint."""
    print("\n🔍 Testing detailed health check...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Detailed health check failed: {e}")
        return False

def test_search_endpoint():
    """Test the search endpoint."""
    print("\n🔍 Testing search endpoint...")
    
    search_data = {
        "query": "Adidas Samba Review",
        "max_results": 5
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/search",
            json=search_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Search test failed: {e}")
        return False

def test_invalid_request():
    """Test invalid request handling."""
    print("\n🚫 Testing invalid request...")
    
    try:
        # Test with missing query
        response = requests.post(
            f"{BASE_URL}/search",
            json={"max_results": 5},
            headers={"Content-Type": "application/json"}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 422  # Validation error
    except Exception as e:
        print(f"❌ Invalid request test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Starting YouTube Search API Tests")
    print(f"🌐 Testing against: {BASE_URL}")
    print("=" * 50)
    
    tests = [
        ("Health Check", test_health_check),
        ("Detailed Health", test_detailed_health),
        ("Search Endpoint", test_search_endpoint),
        ("Invalid Request", test_invalid_request),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        result = test_func()
        results.append((test_name, result))
        print(f"{'✅ PASSED' if result else '❌ FAILED'}: {test_name}")
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status}: {test_name}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed!")
        return 1

if __name__ == "__main__":
    exit(main()) 
