import requests
import json

# 测试单症状API - 打印原始响应
url = "http://localhost:8000/api/diagnosis/start"

data = {
    "patient": {
        "age": 35,
        "gender": "male",
        "history": "",
        "allergies": ""
    },
    "symptoms": [
        {
            "description": "头痛",
            "duration_years": 0,
            "duration_months": 1,
            "duration_days": 0,
            "severity": 2
        }
    ]
}

print("正在测试...")
try:
    response = requests.post(url, json=data, timeout=90)
    result = response.json()
    
    # 打印原始响应
    print(json.dumps(result, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"错误: {e}")
