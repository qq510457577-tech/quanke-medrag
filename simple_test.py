#!/usr/bin/env python
"""简单测试追问"""
import httpx
import json

# 先启动一个诊断
url = "http://localhost:8000/api/diagnosis/start"
headers = {"Content-Type": "application/json"}
data = {
    "patient": {"age": 65, "gender": "male", "history": "高血压"},
    "symptoms": [{"description": "头晕1个月", "duration_years": 0, "duration_months": 1, "severity": 2}]
}

with httpx.Client(timeout=120.0) as client:
    r1 = client.post(url, headers=headers, json=data)
    result = r1.json()
    sid = result["session_id"]
    print(f"Session: {sid}")
    print(f"Questions: {len(result['current_questions'])}")
    
    # 发送追问
    q = result['current_questions'][0]
    answers = [{"question_id": q['question_id'], "question": q['question'], "answer": "是", "answer_type": q['input_type']}]
    
    r2 = client.post("http://localhost:8000/api/diagnosis/follow-up", 
                     headers=headers, 
                     json={"session_id": sid, "answers": answers})
    print(f"Status: {r2.status_code}")
    if r2.status_code != 200:
        print(f"Error: {r2.text}")
    else:
        print(f"Success: {json.dumps(r2.json(), ensure_ascii=False)[:500]}")
