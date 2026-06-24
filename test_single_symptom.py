import requests
import json

# 测试单症状API
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

print("正在测试单症状诊断...")
try:
    response = requests.post(url, json=data, timeout=90)
    result = response.json()
    
    print("\n=== 诊断假设 ===")
    for diag in result.get("differential_diagnoses", [])[:3]:
        print(f"- {diag.get('disease')}: {diag.get('confidence')}%")

    print("\n=== 第一轮问题 ===")
    questions = result.get("first_round_questions", [])
    print(f"共 {len(questions)} 个问题")
    for i, q in enumerate(questions, 1):
        print(f"\n问题{i}: {q.get('question')}")
        print(f"  针对症状: {q.get('target_symptom', '未指定')}")
        print(f"  针对诊断: {q.get('target_disease')}")
        print(f"  类型: {q.get('input_type')}")
except Exception as e:
    print(f"错误: {e}")
