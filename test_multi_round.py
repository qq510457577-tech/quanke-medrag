import json
import requests

# 完整测试
BASE_URL = "http://localhost:8000"

# 启动诊断
data = {
    "patient": {"age": 50, "gender": "male", "history": "", "allergies": ""},
    "symptoms": [{"description": "头痛", "duration_years": 0, "duration_months": 1, "duration_days": 0, "severity": 2}]
}

print("1. 启动诊断...")
r1 = requests.post(f"{BASE_URL}/api/diagnosis/start", json=data, timeout=120)
j1 = r1.json()
sid = j1.get("session_id")
print(f"   Session: {sid}")
print(f"   问题数: {len(j1.get('current_questions', []))}")
print(f"   诊断假设: {[d.get('disease') for d in j1.get('differential_diagnoses', [])[:3]]}")

# 回答问题
print("\n2. 第一轮追问...")
questions = j1.get("current_questions", [])
if questions:
    ans = []
    for q in questions[:3]:  # 回答前3个问题
        if q.get("input_type") == "yesno":
            ans.append({"question_id": q.get("question_id"), "question": q.get("question"), "answer": "是", "answer_type": "yesno"})
        elif q.get("input_type") == "single":
            options = q.get("options", [])
            ans.append({"question_id": q.get("question_id"), "question": q.get("question"), "answer": options[0] if options else "是", "answer_type": "single"})
        else:
            ans.append({"question_id": q.get("question_id"), "question": q.get("question"), "answer": "是", "answer_type": "yesno"})
    
    r2 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans}, timeout=120)
    print(f"   状态: {r2.status_code}")
    if r2.status_code == 200:
        j2 = r2.json()
        print(f"   新问题数: {len(j2.get('next_round_questions', []))}")
        print(f"   诊断清晰: {j2.get('is_diagnosis_clear')}")
        print(f"   当前诊断: {[d.get('disease') for d in j2.get('current_diagnoses', [])[:3]]}")
        
        # 第二轮追问
        questions2 = j2.get("next_round_questions", [])
        if questions2 and not j2.get('is_diagnosis_clear'):
            print("\n3. 第二轮追问...")
            ans2 = []
            for q in questions2[:3]:
                if q.get("input_type") == "yesno":
                    ans2.append({"question_id": q.get("question_id"), "question": q.get("question"), "answer": "否", "answer_type": "yesno"})
                elif q.get("input_type") == "single":
                    options = q.get("options", [])
                    ans2.append({"question_id": q.get("question_id"), "question": q.get("question"), "answer": options[0] if options else "否", "answer_type": "single"})
                else:
                    ans2.append({"question_id": q.get("question_id"), "question": q.get("question"), "answer": "否", "answer_type": "yesno"})
            
            r3 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans2}, timeout=120)
            print(f"   状态: {r3.status_code}")
            if r3.status_code == 200:
                j3 = r3.json()
                print(f"   新问题数: {len(j3.get('next_round_questions', []))}")
                print(f"   诊断清晰: {j3.get('is_diagnosis_clear')}")
                print(f"   当前诊断: {[d.get('disease') for d in j3.get('current_diagnoses', [])[:3]]}")

print("\n测试完成！")
