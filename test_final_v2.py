import json
import requests
import time

# 测试final接口
BASE_URL = "http://localhost:8000"

# 启动诊断
data = {
    "patient": {"age": 50, "gender": "male", "history": "", "allergies": ""},
    "symptoms": [{"description": "头痛", "duration_years": 0, "duration_months": 1, "duration_days": 0, "severity": 2}]
}

print("1. 启动诊断...")
start = time.time()
r1 = requests.post(f"{BASE_URL}/api/diagnosis/start", json=data, timeout=120)
print(f"   耗时: {time.time()-start:.2f}秒")
j1 = r1.json()
sid = j1.get("session_id")
print(f"   Session: {sid}")

# 快速3轮追问
questions = j1.get("current_questions", [])
for round_num in range(1, 4):
    ans = []
    for q in questions:
        options = q.get("options", [])
        ans.append({
            "question_id": q.get("question_id"), 
            "question": q.get("question"), 
            "answer": options[0] if options else "是", 
            "answer_type": q.get("input_type", "single")
        })
    
    print(f"\n{round_num}. 第{round_num}轮追问...")
    start = time.time()
    r2 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans}, timeout=120)
    print(f"   耗时: {time.time()-start:.2f}秒")
    j2 = r2.json()
    print(f"   状态: {r2.status_code}")
    print(f"   诊断清晰: {j2.get('is_diagnosis_clear')}")
    
    questions = j2.get("next_round_questions", [])
    if not questions:
        break

# 测试final接口
print("\n获取最终诊断...")
start = time.time()
r3 = requests.post(f"{BASE_URL}/api/diagnosis/final", json={"session_id": sid, "answers": []}, timeout=120)
print(f"   耗时: {time.time()-start:.2f}秒")
print(f"   状态: {r3.status_code}")
if r3.status_code != 200:
    print(f"   错误: {r3.text}")
else:
    j3 = r3.json()
    print(f"   诊断数: {len(j3.get('diagnoses', []))}")
    if j3.get('diagnoses'):
        print(f"   主要诊断: {j3['diagnoses'][0].get('disease')}")
        print(f"   置信度: {j3['diagnoses'][0].get('confidence')}%")
    print("   成功!")
