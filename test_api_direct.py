import requests
import json

# 测试API
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
            "severity": 3
        }
    ]
}

response = requests.post(url, json=data)
result = response.json()

print("=== 诊断分析 ===")
print(result.get("symptom_analysis", ""))
print("\n=== 风险分层 ===")
print(result.get("risk_stratification", ""))
print("\n=== 诊断假设 ===")
for diag in result.get("differential_diagnoses", []):
    print(f"- {diag.get('disease')}: {diag.get('confidence')}%")
    print(f"  推理: {diag.get('reasoning', '')[:100]}...")

print("\n=== 第一轮问题数量 ===")
questions = result.get("first_round_questions", [])
print(f"共 {len(questions)} 个问题")
for i, q in enumerate(questions, 1):
    print(f"\n问题{i}: {q.get('question')}")
    print(f"  类型: {q.get('input_type')}")
    print(f"  选项: {q.get('options')}")
    print(f"  目标: {q.get('target_disease')}")
