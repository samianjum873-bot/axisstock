#!/usr/bin/env python3
"""Test mobile UI rendering."""
import requests
import sys

BASE_URL = "http://localhost:8000"

def test_login_mobile():
    """Test mobile login page."""
    resp = requests.get(f"{BASE_URL}/login?mobile=1")
    print(f"Status: {resp.status_code}")
    print("\n--- First 500 chars of HTML ---")
    print(resp.text[:500])
    
    # Check if it's the mobile template
    if "mobile/base.html" in resp.text or "AxisStock Mobile" in resp.text or "mobile-container" in resp.text:
        print("\n✅ Mobile template detected!")
        return True
    else:
        print("\n❌ Desktop template rendered (not mobile)")
        return False

if __name__ == "__main__":
    try:
        success = test_login_mobile()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
