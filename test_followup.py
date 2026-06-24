import requests
import json

# 测试追问接口
BASE_URL = "http://localhost:8000"

# 第一轮
data = {
    "patient": {"age": 78, "gender": "male", "history": "高血压8年", "allergies": "青霉素"},
    "symptoms": [
        {"description": "发热", "duration_years": 0, "duration_months": 3, "duration_days": 0, "severity": 3},
        {"description": "心悸", "duration_years": 0, "duration_months": 0, "duration_days": 5, "severity": 3}
    ]
}

print("=== 第一轮 ===")
response = requests.post(f"{BASE_URL}/api/diagnosis/start", json=data, timeout=120)
result = response.json()
session_id = result.get("session_id")
print(f"Session ID: {session_id}")

# 获取第一轮问题
questions = result.get("current_questions", [])
print(f"问题数量: {len(questions)}")

# 模拟回答 - 使用选项
answers = []
for q in questions:
    if q.get("input_type") == "single":
        # 选择第一个选项
        answers.append({
            "question_id": q.get("question_id"),
            "question": q.get("question"),
            "answer": q.get("options", [])[0] if q.get("options") else "A",
            "answer_type": q.get("input_type")
        })
    elif q.get("input_type") == "multiple":
        # 选择第一个选项
        answers.append({
            "question_id": q.get("question_id"),
            "question": q.get("question"),
            "answer": [q.get("options", [])[0]] if q.get("options") else ["A"],
            "answer_type": q.get("input_type")
        })
    elif q.get("input_type") == "yesno":
        answers.append({
            "question_id": q.get("question_id"),
            "question": q.get("question"),
            "answer": "是",
            "answer_type": q.get("input_type")
        })

print(f"\n回答: {json.dumps(answers, ensure_ascii=False)[:200]}...")

# 第二轮追问
print("\n=== 第二轮 ===")
try:
    response2 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", 
        json={"session_id": session_id, "answers": answers}, timeout=120)
    print(f"状态码: {response2.status_code}")
    if response2.status_code == 200:
        result2 = response2.json()
        print(f"诊断假设: {len(result2.get('differential_diagnoses', []))}个")
        print(f"新问题: {len(result2.get('next_round_questions', []))}个")
    else:
        print(f"错误: {response2.text[:200]}")
except Exception as e:
    print(f"错误: {e}")
