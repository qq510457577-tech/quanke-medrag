import requests
import traceback

# 测试追问接口详细错误
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

# 简单回答
answers = [
    {"question_id": "q1", "question": "发热", "answer": "A. 低热", "answer_type": "single"},
    {"question_id": "q2", "question": "心悸", "answer": "B. 快速", "answer_type": "single"},
    {"question_id": "q3", "question": "伴随症状", "answer": ["A. 体重下降"], "answer_type": "multiple"},
    {"question_id": "q4", "question": "降压药", "answer": "C. 在服药", "answer_type": "single"}
]

# 第二轮追问
print("\n=== 第二轮 ===")
try:
    response2 = requests.post(f"{BASE_URL}/api/diagnosis/follow-up", 
        json={"session_id": session_id, "answers": answers}, timeout=120)
    print(f"状态码: {response2.status_code}")
    print(f"响应: {response2.text[:500]}")
except Exception as e:
    print(f"异常: {e}")
    traceback.print_exc()
