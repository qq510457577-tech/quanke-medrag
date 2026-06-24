import requests
import json

# 简单测试
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

# 回答问题 - 简单格式
q1 = j1.get("current_questions", [])[0]
ans = [{"question_id": q1.get("question_id"), "question": q1.get("question"), "answer": "是", "answer_type": "yesno"}]

print("\n2. 追问...")
r2 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", json={"session_id": sid, "answers": ans}, timeout=120)
print(f"   状态: {r2.status_code}")
if r2.status_code != 200:
    print(f"   错误: {r2.text}")
else:
    j2 = r2.json()
    print(f"   新问题: {len(j2.get('next_round_questions', []))}")
