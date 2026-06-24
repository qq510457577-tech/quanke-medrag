import requests

# 测试问题类型
url = "http://localhost:8000/api/diagnosis/start"

data = {
    "patient": {"age": 78, "gender": "male", "history": "高血压8年", "allergies": "青霉素"},
    "symptoms": [
        {"description": "发热", "duration_years": 0, "duration_months": 3, "duration_days": 0, "severity": 3},
        {"description": "心悸", "duration_years": 0, "duration_months": 0, "duration_days": 5, "severity": 3}
    ]
}

print("测试问题类型...")
response = requests.post(url, json=data, timeout=120)
result = response.json()

print("\n=== 第一轮问题 ===")
for i, q in enumerate(result.get("current_questions", []), 1):
    print(f"\n问题{i}: {q.get('question')[:60]}...")
    print(f"  类型: {q.get('input_type')}")
    print(f"  选项: {q.get('options')}")
