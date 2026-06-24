#!/usr/bin/env python
"""测试API健康状态"""
import httpx
import json

url = "http://localhost:8000/docs"

try:
    print("Checking server health...")
    with httpx.Client(timeout=10.0) as client:
        response = client.get(url)
    print(f"Status code: {response.status_code}")
    print("Server is running!")
except Exception as e:
    print(f"Server may have stopped: {e}")
