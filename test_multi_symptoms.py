import requests
import json

# 测试多症状API
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
result = response.json()

print("\n=== 症状分析 ===")
print(result.get("symptom_analysis", ""))

print("\n=== 症状诊断映射 ===")
mapping = result.get("symptom_diagnosis_mapping", {})
for symptom, diagnoses in mapping.items():
    print(f"- {symptom}: {diagnoses}")

print("\n=== 诊断假设 ===")
for diag in result.get("differential_diagnoses", []):
    print(f"- {diag.get('disease')}: {diag.get('confidence')}%")
    print(f"  相关症状: {diag.get('related_symptoms', [])}")
    print(f"  推理: {diag.get('reasoning', '')[:80]}...")

print("\n=== 第一轮问题 ===")
questions = result.get("first_round_questions", [])
print(f"共 {len(questions)} 个问题")
for i, q in enumerate(questions, 1):
    print(f"\n问题{i}: {q.get('question')}")
    print(f"  针对症状: {q.get('target_symptom', '未指定')}")
    print(f"  针对诊断: {q.get('target_disease')}")
    print(f"  类型: {q.get('input_type')}")
    if q.get('options'):
        print(f"  选项: {q.get('options')}")
