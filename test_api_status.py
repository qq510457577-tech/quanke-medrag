import requests

# 测试API是否正常
url = "http://localhost:8000/api/diagnosis/start"

data = {
    "patient": {"age": 78, "gender": "male", "history": "高血压8年", "allergies": "青霉素过敏"},
    "symptoms": [
        {"description": "发热", "duration_years": 0, "duration_months": 3, "duration_days": 0, "severity": 3},
        {"description": "心悸", "duration_years": 0, "duration_months": 0, "duration_days": 5, "severity": 3}
    ]
}

print("测试API...")
try:
    response = requests.post(url, json=data, timeout=120)
    result = response.json()
    print("返回结果:")
    print(f"- session_id: {result.get('session_id', '无')}")
    print(f"- 诊断假设数量: {len(result.get('differential_diagnoses', []))}")
    print(f"- 问题数量: {len(result.get('current_questions', []))}")
    print(f"- 推理链: {result.get('reasoning_chain', '')[:100] if result.get('reasoning_chain') else '无'}...")
except Exception as e:
    print(f"错误: {e}")
