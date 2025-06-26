#!/usr/bin/env python3
"""
Test script for filename parsing functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import extract_search_query_from_filename

def test_filename_parsing():
    """Test the filename parsing function with various formats"""
    
    test_cases = [
        # Expected format: search_query_YYYYMMDD_HHMMSS.json
        ("Adidas_Samba_Review_20241201_143022.json", "Adidas Samba Review"),
        ("Nike_Air_Max_20241201_143022.json", "Nike Air Max"),
        ("Best_Running_Shoes_2024_20241201_143022.json", "Best Running Shoes 2024"),
        
        # Edge cases
        ("simple_query_20241201_143022.json", "simple query"),
        ("query_with_numbers_123_20241201_143022.json", "query with numbers 123"),
        ("single_word_20241201_143022.json", "single word"),
        
        # Fallback cases
        ("unknown_format.json", "unknown format"),
        ("no_timestamp_file.json", "no timestamp file"),
        ("just_numbers_123456.json", "just numbers"),
    ]
    
    print("🧪 Testing filename parsing...")
    print("=" * 50)
    
    all_passed = True
    
    for filename, expected_query in test_cases:
        try:
            result = extract_search_query_from_filename(filename)
            status = "✅" if result == expected_query else "❌"
            print(f"{status} {filename}")
            print(f"   Expected: '{expected_query}'")
            print(f"   Got:      '{result}'")
            
            if result != expected_query:
                all_passed = False
                
        except Exception as e:
            print(f"❌ {filename} - Error: {e}")
            all_passed = False
        
        print()
    
    print("=" * 50)
    if all_passed:
        print("🎉 All tests passed!")
    else:
        print("💥 Some tests failed!")
    
    return all_passed

if __name__ == "__main__":
    test_filename_parsing() 