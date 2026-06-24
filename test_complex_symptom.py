import json
import requests

# 复杂测试 - 用户之前提供的数据
BASE_URL = "http://localhost:8000"

# 启动诊断 - 78岁男，高血压8年，青霉素过敏
data = {
    "patient": {
        "age": 78, 
        "gender": "male", 
        "history": "高血压8年", 
        "allergies": "青霉素过敏"
    },
    "symptoms": [
        {"description": "发热", "duration_years": 0, "duration_months": 3, "duration_days": 0, "severity": 3},
        {"description": "心悸", "duration_years": 0, "duration_months": 0, "duration_days": 5, "severity": 3},
        {"description": "失眠多梦", "duration_years": 0, "duration_months": 0, "duration_days": 2, "severity": 5},
        {"description": "腿沉重", "duration_years": 2, "duration_months": 5, "duration_days": 0, "severity": 4}
    ]
}

print("1. 启动诊断（复杂症状测试）...")
r1 = requests.post(f"{BASE_URL}/api/diagnosis/start", json=data, timeout=120)
j1 = r1.json()
sid = j1.get("session_id")
print(f"   Session: {sid}")
print(f"   问题数: {len(j1.get('current_questions', []))}")
print(f"   诊断假设: {[d.get('disease') for d in j1.get('differential_diagnoses', [])[:5]]}")

# 回答问题
print("\n2. 第一轮追问...")
questions = j1.get("current_questions", [])
if questions:
    ans = []
    for q in questions[:3]:
        options = q.get("options", [])
        ans.append({
            "question_id": q.get("question_id"), 
            "question": q.get("question"), 
            "answer": options[0] if options else "是", 
            "answer_type": q.get("input_type", "single")
        })
    
    r2 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans}, timeout=120)
    print(f"   状态: {r2.status_code}")
    if r2.status_code == 200:
        j2 = r2.json()
        print(f"   新问题数: {len(j2.get('next_round_questions', []))}")
        print(f"   诊断清晰: {j2.get('is_diagnosis_clear')}")
        print(f"   当前诊断: {[d.get('disease') for d in j2.get('current_diagnoses', [])[:5]]}")
        
        # 第二轮追问
        questions2 = j2.get("next_round_questions", [])
        if questions2 and not j2.get('is_diagnosis_clear'):
            print("\n3. 第二轮追问...")
            ans2 = []
            for q in questions2[:3]:
                options = q.get("options", [])
                ans2.append({
                    "question_id": q.get("question_id"), 
                    "question": q.get("question"), 
                    "answer": options[0] if options else "是", 
                    "answer_type": q.get("input_type", "single")
                })
            
            r3 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans2}, timeout=120)
            print(f"   状态: {r3.status_code}")
            if r3.status_code == 200:
                j3 = r3.json()
                print(f"   新问题数: {len(j3.get('next_round_questions', []))}")
                print(f"   诊断清晰: {j3.get('is_diagnosis_clear')}")
                print(f"   当前诊断: {[d.get('disease') for d in j3.get('current_diagnoses', [])[:5]]}")

print("\n复杂症状测试完成！")
