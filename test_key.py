import requests

# 测试API
url = "http://localhost:8000/api/diagnosis/start"

data = {
    "patient": {"age": 78, "gender": "male", "history": "高血压8年", "allergies": "青霉素过敏"},
    "symptoms": [
        {"description": "发热", "duration_years": 0, "duration_months": 3, "duration_days": 0, "severity": 3}
    ]
}

print("测试API...")
try:
    response = requests.post(url, json=data, timeout=120)
    result = response.json()
    print(f"成功! 返回诊断假设: {len(result.get('differential_diagnoses', []))}个")
except Exception as e:
    print(f"错误: {e}")
