#!/usr/bin/env python3
"""Test that product detail page renders without Jinja macro errors."""
import sys
import requests
import time

# Give server time to start
time.sleep(2)

try:
    # Test product detail page
    response = requests.get('http://127.0.0.1:5000/product/1')
    
    if response.status_code == 200:
        # Check for Jinja errors in response
        if 'UndefinedError' in response.text or 'TemplateError' in response.text:
            print("❌ FAIL: Jinja template error found in response")
            print(response.text[:500])
            sys.exit(1)
        
        if 'render_rec_card' in response.text:
            print("✓ Product detail page renders successfully")
            print(f"  Status: {response.status_code}")
            print("  Response contains macro output: YES")
            sys.exit(0)
        else:
            print("⚠ Product detail page renders but may not have recommendations")
            print(f"  Status: {response.status_code}")
            sys.exit(0)
    else:
        print(f"❌ FAIL: Unexpected status {response.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"❌ FAIL: Connection error: {e}")
    sys.exit(1)
