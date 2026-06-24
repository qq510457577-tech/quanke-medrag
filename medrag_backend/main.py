"""
全科医生辅助诊断系统 - 后端服务
基于 MedRAG 思想，针对未分化疾病进行辅助诊断
支持症状拆解、疾病匹配、智能补问流程
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

# ==================== 配置 ====================
app = FastAPI(title="全科医生辅助诊断系统", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ==================== 数据模型 ====================
class SymptomInput(BaseModel):
    """症状输入模型"""
    description: str  # 症状描述
    duration: Optional[str] = None  # 持续时间
    severity: Optional[str] = None  # 严重程度
    location: Optional[str] = None  # 疼痛位置
    additional_info: Optional[Dict[str, Any]] = {}  # 附加信息

class DiagnosisRequest(BaseModel):
    """诊断请求模型"""
    patient_id: Optional[str] = None
    symptoms: List[SymptomInput]
    history: Optional[str] = None  # 病史
    age: Optional[int] = None
    gender: Optional[str] = None

class FollowUpAnswer(BaseModel):
    """补问回答模型"""
    question_id: str
    answer: str

class DiagnosisSession(BaseModel):
    """诊断会话模型"""
    session_id: str
    original_symptoms: List[SymptomInput]
    follow_up_answers: List[FollowUpAnswer] = []
    diagnosis_result: Optional[Dict[str, Any]] = None

# ==================== 医学知识库（简化版） ====================
# 未分化疾病分类知识库
DISEASE_KNOWLEDGE = {
    "呼吸系统": {
        "level1": "呼吸系统疾病",
        "level2": {
            "上呼吸道感染": {
                "level3": "普通感冒",
                "symptoms": ["发热", "咳嗽", "咽痛", "鼻塞", "流涕", "头痛"],
                "key_questions": [
                    "发热是多少度？",
                    "咳嗽有痰还是干咳？",
                    "症状持续几天了？",
                    "是否有咽干或咽痒感？"
                ]
            },
            "流感": {
                "level3": "流行性感冒",
                "symptoms": ["高热", "全身酸痛", "乏力", "头痛", "咳嗽", "咽痛"],
                "key_questions": [
                    "是否突然发病，症状发展迅速？",
                    "是否有明显的全身酸痛和乏力？",
                    "周围有人感冒或流感吗？",
                    "是否接种过流感疫苗？"
                ]
            }
        }
    },
    "消化系统": {
        "level1": "消化系统疾病",
        "level2": {
            "急性胃炎": {
                "level3": "急性胃炎",
                "symptoms": ["上腹痛", "恶心", "呕吐", "腹胀", "食欲不振"],
                "key_questions": [
                    "腹痛是持续还是阵发？",
                    "是否有反酸或烧心感？",
                    "呕吐物是什么颜色？",
                    "最近饮食有什么异常？"
                ]
            },
            "功能性消化不良": {
                "level3": "功能性消化不良",
                "symptoms": ["上腹部不适", "饱胀", "嗳气", "早饱", "恶心"],
                "key_questions": [
                    "症状与情绪压力是否相关？",
                    "饭后症状是否加重？",
                    "是否伴有体重下降？"
                ]
            }
        }
    },
    "心血管系统": {
        "level1": "心血管系统疾病",
        "level2": {
            "心绞痛": {
                "level3": "心绞痛",
                "symptoms": ["胸痛", "胸闷", "气短", "心悸", "出汗"],
                "key_questions": [
                    "胸痛在活动时还是休息时发生？",
                    "胸痛持续多长时间？",
                    "含服硝酸甘油是否缓解？",
                    "疼痛是否向左肩或左上肢放射？"
                ]
            },
            "高血压": {
                "level3": "原发性高血压",
                "symptoms": ["头痛", "头晕", "头胀", "耳鸣", "心悸", "乏力"],
                "key_questions": [
                    "平时血压多少？",
                    "是否服用降压药？",
                    "近期血压波动大吗？",
                    "是否有家族高血压病史？"
                ]
            }
        }
    },
    "神经系统": {
        "level1": "神经系统疾病",
        "level2": {
            "偏头痛": {
                "level3": "偏头痛",
                "symptoms": ["头痛", "恶心", "呕吐", "畏光", "畏声"],
                "key_questions": [
                    "头痛是单侧还是双侧？",
                    "头痛前是否有眼前闪光或暗点？",
                    "头痛时是否愿意在安静暗处休息？",
                    "是否有家族偏头痛病史？"
                ]
            },
            "紧张性头痛": {
                "level3": "紧张性头痛",
                "symptoms": ["头痛", "头晕", "乏力", "失眠", "记忆力减退"],
                "key_questions": [
                    "头痛是否与工作压力或情绪相关？",
                    "头痛是否从后颈部向前额蔓延？",
                    "是否伴有肩颈部肌肉僵硬？",
                    "按摩或热敷是否能缓解？"
                ]
            }
        }
    },
    "肌肉骨骼系统": {
        "level1": "肌肉骨骼系统疾病",
        "level2": {
            "腰椎间盘突出": {
                "level3": "腰椎间盘突出症",
                "symptoms": ["腰痛", "下肢放射痛", "麻木", "无力", "活动受限"],
                "key_questions": [
                    "腰痛是否向臀部或腿部放射？",
                    "站立或行走时症状是否加重？",
                    "平卧休息是否能缓解？",
                    "是否有下肢麻木或无力感？"
                ]
            },
            "骨关节炎": {
                "level3": "骨关节炎",
                "symptoms": ["关节疼痛", "僵硬", "肿胀", "活动受限", "摩擦感"],
                "key_questions": [
                    "哪些关节疼痛？",
                    "早晨起床后关节僵硬持续多长时间？",
                    "活动后症状是加重还是减轻？",
                    "是否有关节肿胀或变形？"
                ]
            }
        }
    }
}

# 通用症状关键词映射
SYMPTOM_KEYWORDS = {
    "发热": ["发烧", "体温高", "发热", "高烧"],
    "咳嗽": ["咳嗽", "干咳", "咳痰", "咳嗽"],
    "胸痛": ["胸痛", "胸口疼", "胸部不适"],
    "腹痛": ["肚子疼", "腹痛", "胃痛", "肚子不舒服"],
    "头痛": ["头痛", "头疼", "头部不适"],
    "腰痛": ["腰痛", "腰疼", "背部疼痛"],
    "乏力": ["乏力", "疲倦", "没力气", "疲劳"],
    "头晕": ["头晕", "眩晕", "头昏", "眼黑"],
    "恶心": ["恶心", "想吐", "反胃"],
    "呕吐": ["呕吐", "吐", "干呕"],
    "腹泻": ["腹泻", "拉肚子", "大便稀"],
    "便秘": ["便秘", "大便干", "排便困难"],
    "心悸": ["心悸", "心跳快", "心跳重"],
    "气短": ["气短", "呼吸困难", "胸闷", "气不够用"],
    "失眠": ["失眠", "睡不着", "睡眠不好", "早醒"],
}

# ==================== DeepSeek API 调用 ====================
async def call_deepseek(prompt: str, system_prompt: str = None) -> str:
    """调用 DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        return "错误：未配置 DeepSeek API Key"

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
                return f"API调用失败：{response.status_code}"
    except Exception as e:
        return f"API调用错误：{str(e)}"

# ==================== 症状分析函数 ====================
def extract_symptom_keywords(description: str) -> List[str]:
    """从症状描述中提取关键词"""
    found_symptoms = []
    description = description.lower()
    
    for symptom, keywords in SYMPTOM_KEYWORDS.items():
        for keyword in keywords:
            if keyword in description:
                if symptom not in found_symptoms:
                    found_symptoms.append(symptom)
                break
    
    return found_symptoms

def match_diseases(symptoms: List[str]) -> Dict[str, Any]:
    """根据症状匹配可能的疾病"""
    matched_diseases = []
    
    for system_key, system_data in DISEASE_KNOWLEDGE.items():
        for disease_key, disease_data in system_data["level2"].items():
            disease_symptoms = disease_data.get("symptoms", [])
            
            # 计算症状匹配度
            matched_count = sum(1 for s in symptoms if s in disease_symptoms)
            if matched_count > 0:
                match_score = matched_count / len(disease_symptoms)
                matched_diseases.append({
                    "system": system_key,
                    "category": disease_key,
                    "disease": disease_data["level3"],
                    "matched_symptoms": [s for s in symptoms if s in disease_symptoms],
                    "match_score": match_score,
                    "key_questions": disease_data.get("key_questions", [])
                })
    
    # 按匹配度排序
    matched_diseases.sort(key=lambda x: x["match_score"], reverse=True)
    
    return matched_diseases

# ==================== API 路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "全科医生辅助诊断系统",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/api/knowledge")
async def get_knowledge():
    """获取医学知识库概览"""
    return {
        "systems": list(DISEASE_KNOWLEDGE.keys()),
        "disease_count": sum(
            len(data["level2"]) 
            for data in DISEASE_KNOWLEDGE.values()
        )
    }

@app.post("/api/analyze")
async def analyze_symptoms(request: DiagnosisRequest):
    """分析症状，返回初步诊断建议和智能补问"""
    # 1. 提取症状关键词
    all_symptoms = []
    for symptom in request.symptoms:
        extracted = extract_symptom_keywords(symptom.description)
        all_symptoms.extend(extracted)
    
    # 去重
    all_symptoms = list(set(all_symptoms))
    
    if not all_symptoms:
        # 如果没有匹配到关键词，使用描述作为上下文
        all_symptoms = [s.description for s in request.symptoms]
    
    # 2. 匹配可能的疾病
    matched_diseases = match_diseases(all_symptoms[:10])
    
    # 3. 生成智能补问
    follow_up_questions = []
    
    # 从匹配疾病中提取补问
    for disease in matched_diseases[:3]:
        for q in disease.get("key_questions", [])[:2]:
            follow_up_questions.append({
                "id": f"q_{len(follow_up_questions) + 1}",
                "question": q,
                "related_disease": disease["disease"],
                "category": disease["category"]
            })
    
    # 4. 使用 DeepSeek 生成综合分析
    patient_info = ""
    if request.age:
        patient_info += f"年龄：{request.age}岁；"
    if request.gender:
        patient_info += f"性别：{request.gender}；"
    if request.history:
        patient_info += f"病史：{request.history}"
    
    symptom_text = "、".join(all_symptoms) if all_symptoms else request.symptoms[0].description
    
    system_prompt = """你是一位经验丰富的全科医生，擅长未分化疾病的诊断。你需要根据患者提供的症状信息，进行专业的医学分析。

请遵循以下原则：
1. 从常见病、多发病角度考虑
2. 注意鉴别相似症状的不同疾病
3. 给出需要进一步明确的问题
4. 始终提醒最终诊断需要医生面诊确定"""

    analysis_prompt = f"""
患者信息：{patient_info}

患者主诉症状：{symptom_text}

请进行分析：
1. 可能的诊断（列出前3个可能的疾病）
2. 需要鉴别的疾病
3. 建议的检查或检验
4. 需要追问的问题（至少3个）

请用简洁专业的语言回答。
"""

    analysis_result = await call_deepseek(analysis_prompt, system_prompt)
    
    # 构建返回结果
    return {
        "session_id": f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "extracted_symptoms": all_symptoms,
        "matched_diseases": matched_diseases[:5],
        "follow_up_questions": follow_up_questions[:6],
        "llm_analysis": analysis_result,
        "patient_info": {
            "age": request.age,
            "gender": request.gender,
            "history": request.history
        }
    }

@app.post("/api/diagnose")
async def final_diagnose(
    session_id: str,
    original_symptoms: List[Dict],
    follow_up_answers: List[FollowUpAnswer]
):
    """根据补充问诊结果，给出最终诊断建议"""
    
    # 整合所有症状和回答
    symptom_text = ""
    for s in original_symptoms:
        symptom_text += f"主诉：{s.get('description', '')}；"
    
    for answer in follow_up_answers:
        symptom_text += f"追问：{answer.question} -> {answer.answer}；"
    
    # 构建诊断提示
    system_prompt = """你是一位全科医生辅助诊断系统，基于患者提供的完整症状信息（包括主诉和追问回答），给出诊断建议。

输出格式要求（严格按照这个格式）：
1. 初步诊断：[诊断名称]
2. 诊断依据：[支持诊断的理由]
3. 鉴别诊断：[需要排除的其他可能疾病]
4. 建议检查：[建议做的检查]
5. 治疗建议：[初步治疗建议]
6. 注意事项：[需要提醒患者注意的事项]

注意：本系统仅供参考，实际诊断必须由执业医师确定。"""

    diagnose_prompt = f"""
患者症状信息汇总：
{symptom_text}

请基于以上完整信息给出诊断建议：
"""

    diagnosis_result = await call_deepseek(diagnose_prompt, system_prompt)
    
    return {
        "session_id": session_id,
        "diagnosis": diagnosis_result,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/chat")
async def chat_diagnosis(message: str, context: Optional[str] = None):
    """对话式诊断接口"""
    
    system_prompt = """你是一位全科医生助手，专门帮助用户初步了解自己的症状可能对应的疾病情况。

请遵循以下原则：
1. 询问详细的症状信息（部位、持续时间、诱因、缓解因素等）
2. 给出初步的分析和建议
3. 提醒用户如有需要应及时就医
4. 不要给出确定的诊断，只提供参考信息
5. 保持友好、耐心的态度"""

    response = await call_deepseek(message, system_prompt)
    
    return {
        "response": response,
        "timestamp": datetime.now().isoformat()
    }

# ==================== 启动配置 ====================
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("全科医生辅助诊断系统")
    print("API 文档：http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
