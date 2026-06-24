import json
import requests

# 测试第二轮追问的完整流程
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
print(f"   初始问题数: {len(j1.get('current_questions', []))}")

# 第一轮追问
questions = j1.get("current_questions", [])
ans = []
for q in questions:
    options = q.get("options", [])
    ans.append({
        "question_id": q.get("question_id"), 
        "question": q.get("question"), 
        "answer": options[0] if options else "是", 
        "answer_type": q.get("input_type", "single")
    })

print("\n2. 第一轮追问...")
r2 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans}, timeout=120)
j2 = r2.json()
print(f"   状态: {r2.status_code}")
print(f"   诊断清晰: {j2.get('is_diagnosis_clear')}")
print(f"   轮次: {j2.get('round_count')}")
print(f"   新问题数: {len(j2.get('next_round_questions', []))}")

# 第二轮追问
questions2 = j2.get("next_round_questions", [])
ans2 = []
for q in questions2:
    options = q.get("options", [])
    ans2.append({
        "question_id": q.get("question_id"), 
        "question": q.get("question"), 
        "answer": options[0] if options else "是", 
        "answer_type": q.get("input_type", "single")
    })

print("\n3. 第二轮追问...")
r3 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans2}, timeout=120)
j3 = r3.json()
print(f"   状态: {r3.status_code}")
print(f"   诊断清晰: {j3.get('is_diagnosis_clear')}")
print(f"   轮次: {j3.get('round_count')}")
print(f"   新问题数: {len(j3.get('next_round_questions', []))}")

# 第三轮追问
questions3 = j3.get("next_round_questions", [])
if questions3:
    ans3 = []
    for q in questions3:
        options = q.get("options", [])
        ans3.append({
            "question_id": q.get("question_id"), 
            "question": q.get("question"), 
            "answer": options[0] if options else "是", 
            "answer_type": q.get("input_type", "single")
        })
    
    print("\n4. 第三轮追问...")
    r4 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans3}, timeout=120)
    j4 = r4.json()
    print(f"   状态: {r4.status_code}")
    print(f"   诊断清晰: {j4.get('is_diagnosis_clear')}")
    print(f"   轮次: {j4.get('round_count')}")
    print(f"   新问题数: {len(j4.get('next_round_questions', []))}")
    
    # 第四轮追问
    questions4 = j4.get("next_round_questions", [])
    if questions4:
        ans4 = []
        for q in questions4:
            options = q.get("options", [])
            ans4.append({
                "question_id": q.get("question_id"), 
                "question": q.get("question"), 
                "answer": options[0] if options else "是", 
                "answer_type": q.get("input_type", "single")
            })
        
        print("\n5. 第四轮追问（最后一轮）...")
        r5 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans4}, timeout=120)
        j5 = r5.json()
        print(f"   状态: {r5.status_code}")
        print(f"   诊断清晰: {j5.get('is_diagnosis_clear')}")
        print(f"   轮次: {j5.get('round_count')}")
        print(f"   返回问题数: {len(j5.get('next_round_questions', []))}")

print("\n测试完成!")
