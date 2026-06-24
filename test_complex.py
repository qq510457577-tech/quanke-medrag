import requests
import json

# 测试复杂多症状案例
url = "http://localhost:8000/api/diagnosis/start"

data = {
    "patient": {
        "age": 78,
        "gender": "male",
        "history": "高血压8年",
        "allergies": "青霉素过敏"
    },
    "symptoms": [
        {
            "description": "发热",
            "duration_years": 0,
            "duration_months": 3,
            "duration_days": 0,
            "severity": 3
        },
        {
            "description": "心悸",
            "duration_years": 0,
            "duration_months": 0,
            "duration_days": 5,
            "severity": 3
        },
        {
            "description": "失眠多梦",
            "duration_years": 0,
            "duration_months": 0,
            "duration_days": 2,
            "severity": 5
        },
        {
            "description": "腿沉重",
            "duration_years": 2,
            "duration_months": 5,
            "duration_days": 0,
            "severity": 4
        }
    ]
}

print("正在测试复杂多症状诊断...")
try:
    response = requests.post(url, json=data, timeout=120)
    result = response.json()
    
    print("\n=== 症状分析 ===")
    print(result.get("symptom_analysis", ""))
    
    print("\n=== 风险分层 ===")
    print(result.get("risk_stratification", ""))

    print("\n=== 诊断假设 ===")
    for diag in result.get("differential_diagnoses", [])[:6]:
        print(f"- {diag.get('disease')}: {diag.get('confidence')}%")
        print(f"  相关症状: {diag.get('related_symptoms', [])}")

    print("\n=== 第一轮问题 ===")
    questions = result.get("current_questions", [])
    print(f"共 {len(questions)} 个问题")
    for i, q in enumerate(questions, 1):
        print(f"\n问题{i}: {q.get('question')[:80]}...")
        print(f"  针对症状: {q.get('target_symptom', '未指定')}")
        print(f"  针对诊断: {q.get('target_disease')}")
        print(f"  类型: {q.get('input_type')}")
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
