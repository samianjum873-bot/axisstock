#!/usr/bin/env python3
"""Test mobile UI rendering."""
import requests
import sys

BASE_URL = "http://localhost:8000"

MOBILE_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

def test_login_mobile():
    """Test mobile login page using a mobile user-agent."""
    resp = requests.get(
        f"{BASE_URL}/login",
        headers={"User-Agent": MOBILE_USER_AGENT},
        timeout=10,
    )
    print(f"Status: {resp.status_code}")
    print("\n--- First 500 chars of HTML ---")
    print(resp.text[:500])
    
    # Check if it's the mobile template
    if "AxisStock Mobile" in resp.text or "mobile-container" in resp.text:
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
