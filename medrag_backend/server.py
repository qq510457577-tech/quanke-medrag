"""
全科医生辅助诊断系统 - 简化版后端
"""
import os
os.environ['DEEPSEEK_API_KEY'] = 'your-deepseek-api-key-here'

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="全科医生辅助诊断系统")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 疾病知识库
DISEASE_KNOWLEDGE = {
    "神经系统": {
        "level1": "神经系统疾病",
        "level2": {
            "头晕待查": {
                "level3": "头晕待查",
                "symptoms": ["头晕", "眩晕", "头昏"],
                "key_questions": [
                    "头晕是否伴有旋转感？",
                    "头晕是否与体位变化有关？",
                    "是否有视物模糊或双影？",
                    "是否有耳鸣或听力下降？",
                    "是否有四肢麻木或无力？"
                ]
            },
            "椎基底动脉供血不足": {
                "level3": "椎基底动脉供血不足",
                "symptoms": ["头晕", "眩晕", "恶心", "呕吐", "视物模糊"],
                "key_questions": [
                    "头晕是否突然发作？",
                    "是否有走路不稳？",
                    "是否有言语不清？"
                ]
            },
            "颈椎病": {
                "level3": "颈椎病",
                "symptoms": ["头晕", "头痛", "颈肩痛", "上肢麻木"],
                "key_questions": [
                    "颈部活动是否受限？",
                    "是否有手臂麻木？",
                    "头晕是否与颈部转动有关？"
                ]
            }
        }
    },
    "心血管系统": {
        "level1": "心血管系统疾病",
        "level2": {
            "高血压": {
                "level3": "原发性高血压",
                "symptoms": ["头晕", "头痛", "头胀", "心悸", "乏力"],
                "key_questions": [
                    "平时血压多少？",
                    "是否服用降压药？",
                    "是否有家族高血压病史？"
                ]
            },
            "低血压": {
                "level3": "低血压",
                "symptoms": ["头晕", "乏力", "心悸", "眼前发黑"],
                "key_questions": [
                    "头晕是否在起身时加重？",
                    "是否有乏力感？",
                    "睡眠质量如何？"
                ]
            }
        }
    }
}

SYMPTOM_KEYWORDS = {
    "头晕": ["头晕", "眩晕", "头昏", "头重", "眼花"],
    "头痛": ["头痛", "头疼", "头胀"],
    "恶心": ["恶心", "想吐", "反胃"],
    "呕吐": ["呕吐", "吐"],
    "乏力": ["乏力", "疲倦", "没力气"],
    "心悸": ["心悸", "心跳快", "心跳重"],
}

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

def extract_symptom_keywords(description):
    found = []
    desc = description.lower()
    for symptom, keywords in SYMPTOM_KEYWORDS.items():
        for kw in keywords:
            if kw in desc:
                if symptom not in found:
                    found.append(symptom)
                break
    return found

def match_diseases(symptoms):
    matched = []
    for sys_key, sys_data in DISEASE_KNOWLEDGE.items():
        for dis_key, dis_data in sys_data["level2"].items():
            dis_symptoms = dis_data.get("symptoms", [])
            matched_count = sum(1 for s in symptoms if s in dis_symptoms)
            if matched_count > 0:
                match_score = matched_count / len(dis_symptoms)
                matched.append({
                    "system": sys_key,
                    "category": dis_key,
                    "disease": dis_data["level3"],
                    "matched_symptoms": [s for s in symptoms if s in dis_symptoms],
                    "match_score": match_score,
                    "key_questions": dis_data.get("key_questions", [])
                })
    matched.sort(key=lambda x: x["match_score"], reverse=True)
    return matched

async def call_deepseek(prompt, system_prompt=None):
    if not DEEPSEEK_API_KEY:
        return "错误：未配置 API Key"
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload
            )
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"API调用失败：{response.status_code} - {response.text[:200]}"
    except Exception as e:
        return f"API调用错误：{str(e)}"

@app.get("/")
async def root():
    return {"name": "全科医生助手", "version": "1.0.0", "status": "running"}

@app.get("/api/knowledge")
async def get_knowledge():
    return {
        "systems": list(DISEASE_KNOWLEDGE.keys()),
        "disease_count": sum(len(data["level2"]) for data in DISEASE_KNOWLEDGE.values())
    }

@app.post("/api/analyze")
async def analyze_symptoms(request: dict):
    symptoms_list = request.get("symptoms", [])
    age = request.get("age")
    gender = request.get("gender")
    history = request.get("history")
    
    # 提取症状关键词
    all_symptoms = []
    for s in symptoms_list:
        desc = s.get("description", "")
        extracted = extract_symptom_keywords(desc)
        all_symptoms.extend(extracted)
    
    all_symptoms = list(set(all_symptoms))
    
    if not all_symptoms:
        all_symptoms = [s.get("description", "") for s in symptoms_list]
    
    # 匹配疾病
    matched_diseases = match_diseases(all_symptoms[:10])
    
    # 生成补问
    follow_up_questions = []
    for disease in matched_diseases[:3]:
        for q in disease.get("key_questions", [])[:2]:
            follow_up_questions.append({
                "id": f"q_{len(follow_up_questions) + 1}",
                "question": q,
                "related_disease": disease["disease"],
                "category": disease["category"]
            })
    
    # 使用DeepSeek生成分析
    patient_info = f"年龄：{age}岁；性别：{gender or '未填写'}；病史：{history or '无'}"
    symptom_text = "、".join(all_symptoms) if all_symptoms else symptoms_list[0].get("description", "")
    
    system_prompt = """你是一位经验丰富的全科医生，擅长未分化疾病的诊断。请根据患者症状进行专业分析。"""
    
    analysis_prompt = f"""
患者信息：{patient_info}
主诉症状：{symptom_text}

请进行分析：
1. 可能的诊断（列出前3个）
2. 需要鉴别的疾病
3. 建议的检查
4. 需要追问的问题（至少3个）
"""
    
    analysis_result = await call_deepseek(analysis_prompt, system_prompt)
    
    return {
        "session_id": f"session_{hash(symptom_text) % 1000000}",
        "extracted_symptoms": all_symptoms,
        "matched_diseases": matched_diseases[:5],
        "follow_up_questions": follow_up_questions[:6],
        "llm_analysis": analysis_result,
        "patient_info": {"age": age, "gender": gender, "history": history}
    }

@app.post("/api/diagnose")
async def final_diagnose(request: dict):
    session_id = request.get("session_id", "default")
    original_symptoms = request.get("original_symptoms", [])
    follow_up_answers = request.get("follow_up_answers", [])
    
    symptom_text = ""
    for s in original_symptoms:
        symptom_text += f"主诉：{s.get('description', '')}；"
    
    for ans in follow_up_answers:
        symptom_text += f"追问：{ans.get('question', '')} -> {ans.get('answer', '')}；"
    
    system_prompt = """你是一位全科医生辅助诊断系统。输出格式：
1. 初步诊断：[诊断名称]
2. 诊断依据：[理由]
3. 鉴别诊断：[需排除的疾病]
4. 建议检查：[检查建议]
5. 治疗建议：[治疗建议]
6. 注意事项：[提醒]

注意：本系统仅供参考，实际诊断必须由执业医师确定。"""
    
    diagnose_prompt = f"患者症状信息：{symptom_text}\n请给出诊断建议："
    
    diagnosis = await call_deepseek(diagnose_prompt, system_prompt)
    
    return {
        "session_id": session_id,
        "diagnosis": diagnosis,
        "timestamp": "2024-01-01T00:00:00"
    }

@app.post("/api/chat")
async def chat_diagnosis(request: dict):
    message = request.get("message", "")
    
    system_prompt = """你是一位全科医生助手。请：
1. 询问详细症状信息
2. 给出初步分析
3. 提醒及时就医
4. 保持友好耐心"""
    
    response = await call_deepseek(message, system_prompt)
    
    return {"response": response, "timestamp": "2024-01-01T00:00:00"}

if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("全科医生辅助诊断系统")
    print("API: http://localhost:8000")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
