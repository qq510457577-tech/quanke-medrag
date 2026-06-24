import requests
import json

# 测试多症状API - 获取完整返回
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
        },
        {
            "description": "发热",
            "duration_years": 0,
            "duration_months": 0,
            "duration_days": 3,
            "severity": 3
        }
    ]
}

print("正在测试多症状诊断...")
response = requests.post(url, json=data, timeout=60)

# 打印完整JSON
print("\n=== 完整返回JSON ===")
result = response.json()
print(json.dumps(result, ensure_ascii=False, indent=2))
