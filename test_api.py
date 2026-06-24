#!/usr/bin/env python
"""测试API调用"""
import httpx
import json

url = "http://localhost:8000/api/diagnosis/start"
headers = {"Content-Type": "application/json"}
data = {
    "patient": {
        "age": 65,
        "gender": "male",
        "history": "高血压10年，糖尿病5年"
    },
    "symptoms": [
        {
            "description": "反复头晕1个月",
            "duration_years": 0,
            "duration_months": 1,
            "duration_days": 0,
            "severity": 2
        }
    ]
}

try:
    print("Sending request to:", url)
    with httpx.Client(timeout=120.0) as client:
        response = client.post(url, headers=headers, json=data)
    print(f"Status code: {response.status_code}")
    print("Response:")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
