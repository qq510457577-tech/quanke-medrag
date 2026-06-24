#!/usr/bin/env python
"""测试急危重症检测"""
import httpx
import json

print("="*70)
print("测试急危重症 - 胸痛")
print("="*70)

url = "http://localhost:8000/api/diagnosis/start"
headers = {"Content-Type": "application/json"}
data = {
    "patient": {"age": 55, "gender": "male", "history": "高血压5年"},
    "symptoms": [{"description": "突发胸痛2小时", "duration_years": 0, "duration_months": 0, "duration_days": 0, "severity": 5}]
}

with httpx.Client(timeout=120.0) as client:
    response = client.post(url, headers=headers, json=data)
    result = response.json()
    
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2500])
