#!/usr/bin/env python
"""测试循证医学诊断系统"""
import httpx
import json

# 测试1: 普通症状
print("="*70)
print("测试1: 普通症状 - 头晕")
print("="*70)

url = "http://localhost:8000/api/diagnosis/start"
headers = {"Content-Type": "application/json"}
data = {
    "patient": {"age": 65, "gender": "male", "history": "高血压10年"},
    "symptoms": [{"description": "反复头晕1个月", "duration_years": 0, "duration_months": 1, "severity": 2}]
}

with httpx.Client(timeout=120.0) as client:
    response = client.post(url, headers=headers, json=data)
    result = response.json()
    
    print(json.dumps(result, indent=2, ensure_ascii=False)[:2000])
