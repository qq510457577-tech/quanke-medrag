import sys
sys.path.insert(0, r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")

import asyncio
import json
from llm_diagnosis import generate_follow_up_questions, DiagnosisSession, PatientInfo, Symptom, FollowUpAnswer

async def test():
    # 创建测试会话
    session = DiagnosisSession("test-session")
    session.patient_info = PatientInfo(age=50, gender="male", history="", allergies="")
    session.symptoms = [Symptom(description="头痛", duration_years=0, duration_months=1, duration_days=0, severity=2)]
    session.diagnosis_hypothesis = [
        {"disease": "偏头痛", "confidence": 40, "reasoning": "症状分析"},
        {"disease": "紧张性头痛", "confidence": 30, "reasoning": "症状分析"}
    ]
    
    # 模拟第一轮回答
    answers = [
        FollowUpAnswer(question_id="q1", question="您头痛多久了？", answer="一个月内", answer_type="single")
    ]
    
    print("开始测试...")
    try:
        result = await generate_follow_up_questions(session, answers)
        print(f"结果类型: {type(result)}")
        print(f"结果内容: {str(result)[:500]}")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
