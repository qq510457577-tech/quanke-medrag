"""
全科医生辅助诊断系统 - 后端服务
基于DeepSeek API实现循证医学临床思维链辅助诊断
遵循：国家卫健委全科医学临床路径、《内科学》教材、WHO诊疗规范
"""

import os
import json
import asyncio
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# ==================== 配置 ====================
app = FastAPI(
    title="全科医生辅助诊断系统",
    version="3.0.0",
    description="循证医学临床思维链辅助诊断系统"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key-here")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ==================== 急危重症识别 ====================
# 需要立即转诊的危急症状
EMERGENCY_SYMPTOMS = {
    "胸痛": "胸痛可能是急性心肌梗死、主动脉夹层、肺栓塞等急症的表现",
    "呼吸困难": "呼吸困难可能是心力衰竭、肺栓塞、气胸、哮喘持续状态等急症",
    "昏迷": "昏迷可能是脑血管意外、中毒、低血糖、脑炎等危重症",
    "大出血": "大出血可能导致失血性休克，需立即抢救",
    "高热惊厥": "高热惊厥需紧急处理，排除脑炎、脑膜炎等",
    "剧烈头痛": "剧烈头痛可能是脑出血、蛛网膜下腔出血、脑膜炎等",
    "意识障碍": "意识障碍可能提示严重神经系统疾病",
    "急性腹痛": "急性腹痛可能是阑尾炎、胰腺炎、宫外孕等急症",
    "呼吸停止": "呼吸停止需立即心肺复苏",
    "心跳停止": "心跳停止需立即心肺复苏",
    "休克": "休克危及生命，需立即抢救",
    "中毒": "中毒需立即处理"
}

# ==================== 数据模型 ====================
class PatientInfo(BaseModel):
    """患者基本信息"""
    age: Optional[int] = None
    gender: Optional[str] = None
    history: Optional[str] = None
    allergies: Optional[str] = None

class Symptom(BaseModel):
    """症状模型"""
    description: str
    duration_years: int = 0
    duration_months: int = 0
    duration_days: int = 0
    severity: int = 1

class DiagnosisRequest(BaseModel):
    """诊断请求"""
    patient: PatientInfo
    symptoms: List[Symptom]
    session_id: Optional[str] = None

class FollowUpAnswer(BaseModel):
    """追问回答"""
    question_id: str
    question: str
    answer: Any
    answer_type: str

class FollowUpRequest(BaseModel):
    """追问请求"""
    session_id: str
    answers: List[FollowUpAnswer]

class DiagnosisSession:
    """诊断会话管理"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.created_at = datetime.now()
        self.patient_info: Optional[PatientInfo] = None
        self.symptoms: List[Symptom] = []
        self.diagnosis_hypothesis: List[Dict] = []
        self.follow_up_rounds: List[Dict] = []
        self.current_questions: List[Dict] = []
        self.all_answers: List[Dict] = []
        self.is_diagnosis_clear = False
        self.conversation_history: List[Dict] = []
        self.round_count = 0
        self.is_emergency = False
        self.emergency_type = None

# 会话存储
sessions: Dict[str, DiagnosisSession] = {}

# ==================== 辅助函数 ====================
def get_gender_text(gender: str) -> str:
    """获取性别文本"""
    if gender == 'male':
        return '男'
    elif gender == 'female':
        return '女'
    return '未填写'

def get_duration_text(years: int, months: int, days: int = 0) -> str:
    """获取持续时间文本"""
    parts = []
    if years > 0:
        parts.append(f"{years}年")
    if months > 0:
        parts.append(f"{months}个月")
    if days > 0 and years == 0 and months == 0:
        parts.append(f"{days}天")
    return "".join(parts) if parts else "未填写"

def get_severity_text(severity: int) -> str:
    """获取严重程度文本"""
    levels = {1: "轻", 2: "较轻", 3: "中", 4: "较重", 5: "重"}
    return levels.get(severity, "未填写")

def check_emergency(symptoms: List[Symptom]) -> tuple:
    """检查是否存在急危重症症状"""
    for symptom in symptoms:
        desc = symptom.description.lower()
        for emergency_key, emergency_desc in EMERGENCY_SYMPTOMS.items():
            if emergency_key in desc:
                return True, emergency_key, emergency_desc
    return False, None, None

# ==================== DeepSeek API调用 ====================
# 创建全局HTTP客户端以复用连接，提升性能
_http_client = None

def get_http_client():
    """获取或创建全局HTTP客户端（连接池复用）"""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=90.0,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers={"Content-Type": "application/json"}
        )
    return _http_client

async def call_deepseek(prompt: str, system_prompt: str = None, max_tokens: int = 2000) -> str:
    """调用DeepSeek API - 优化版（连接复用）"""
    if not system_prompt:
        system_prompt = """你是一位资深循证全科医学专家，擅长通过标准化临床思维链开展疾病辅助诊断。

工作原则：
1. 严格按照「症状收集→诱因/既往史梳理→鉴别诊断→辅助检查建议→初步确诊」流程
2. 优先引用国家卫健委全科医学临床路径、《内科学》统编教材、WHO相关诊疗规范
3. 对未分化疾病，仅开展鉴别分析，设计定向追问问题
4. 诊断结论必须明确「诊断名称+置信度+核心依据」
5. 区分「必查项目」和「可选/进阶项目」

行为红线：
1. 不开具具体处方剂量、用药频次
2. 急危重症优先标注「急诊/立即转诊」
3. 语言严谨、客观，不夸大病情
4. 严格遵循JSON格式输出"""

    headers = {
        "Authorization": "Bearer {}".format(DEEPSEEK_API_KEY)
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": max_tokens
    }
    
    # 使用全局客户端，复用连接
    client = get_http_client()
    try:
        response = await client.post(
            DEEPSEEK_BASE_URL + "/v1/chat/completions",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print("DeepSeek API调用失败: {}".format(e))
        raise HTTPException(status_code=500, detail="AI诊断服务调用失败: {}".format(str(e)))

# ==================== 循证医学系统提示词 ====================
EVIDENCE_BASED_SYSTEM_PROMPT = """你是一位资深循证全科医学专家，擅长通过标准化临床思维链开展疾病辅助诊断。

【核心原则】
1. 严格按照「症状收集→诱因/既往史梳理→鉴别诊断→辅助检查建议→初步确诊」分步推进
2. 所有诊断依据优先引用国家卫健委全科医学临床路径、《内科学》统编教材、WHO相关诊疗规范
3. 对症状不典型的未分化疾病，不随意下诊断，仅开展鉴别分析，设计定向追问问题
4. 诊断结论必须明确「诊断名称+置信度（0-100%）+核心依据」
5. 根据症状严重程度，明确给出「必查项目」和「可选/进阶项目」

【行为红线】（严格遵守）
1. 不开具具体处方剂量、用药频次，不做最终确诊，仅提供辅助诊断和合理建议
2. 对急危重症（如胸痛、呼吸困难、昏迷、大出血、高热惊厥等），优先在「风险分层」标注「急诊/立即转诊」
3. 语言严谨、客观，不夸大病情、不恐吓患者，不使用模糊、不确定的表述
4. 严格遵循JSON格式输出，字段完整、无语法错误

【循证依据引用格式】
- 国内指南：国家卫健委《XXX临床路径》、《中国XXX诊疗指南202X》
- 教材：《内科学》第9版，人民卫生出版社
- WHO规范：WHO《XXX management guideline》
"""

# ==================== LLM临床思维链核心功能 ====================

async def generate_initial_diagnosis(request: DiagnosisRequest) -> Dict:
    """使用LLM生成初始诊断假设和第一轮问题"""
    
    # 首先检查是否存在急危重症
    is_emergency, emergency_type, emergency_desc = check_emergency(request.symptoms)
    
    # 如果是急危重症，直接返回紧急处理建议，不继续追问
    if is_emergency:
        return {
            "symptom_analysis": "患者存在危急症状：{}".format(emergency_type),
            "is_emergency": True,
            "emergency_type": emergency_type,
            "emergency_warning": emergency_desc,
            "risk_stratification": "急诊/立即转诊",
            "emergency_action": "请立即前往急诊或拨打120急救电话",
            "differential_diagnoses": [],
            "first_round_questions": [],
            "reasoning_chain": "根据症状分析，患者存在{}，属于急危重症范畴，需立即转诊急诊处理，不适合继续追问".format(emergency_type),
            "required_examinations": [],
            "optional_examinations": [],
            "disclaimer": "本系统仅提供辅助诊断参考，不替代面诊，需立即就医"
        }
    
    # 构建患者信息
    gender_text = get_gender_text(request.patient.gender)
    age = request.patient.age or '未填写'
    
    # 年龄相关分析
    age_analysis = ""
    if age and isinstance(age, int):
        if age >= 65:
            age_analysis = "老年患者：需特别关注心脑血管疾病、神经系统退行性变、多病共存、药物代谢变化"
        elif age < 18:
            age_analysis = "未成年患者：需考虑先天性疾病、生长发育相关问题、儿科特有疾病"
        elif age >= 45:
            age_analysis = "中年患者：需关注代谢性疾病、心血管风险、肿瘤筛查"
    
    patient_info = """
【患者基本信息】
- 年龄：{}岁
- 性别：{}
- 既往病史：{}
- 过敏史：{}

【年龄相关考虑】
{}
""".format(
        age,
        gender_text,
        request.patient.history or '无',
        request.patient.allergies or '无',
        age_analysis or '无特殊考虑'
    )
    
    # 构建症状信息
    symptoms_info = "\n【症状描述】（共{}个症状）\n".format(len(request.symptoms))
    for i, s in enumerate(request.symptoms, 1):
        duration = get_duration_text(s.duration_years, s.duration_months, s.duration_days or 0)
        severity = get_severity_text(s.severity)
        symptoms_info += "症状{}: {}（持续时间：{}，严重程度：{}级）\n".format(
            i, s.description, duration, severity
        )
    
    # 添加多症状关联分析说明
    if len(request.symptoms) > 1:
        symptom_names = "、".join([s.description for s in request.symptoms])
        symptoms_info += "\n【多症状综合分析要求】\n"
        symptoms_info += "患者同时存在以下症状：{}。\n".format(symptom_names)
        symptoms_info += "这些症状可能：\n"
        symptoms_info += "1. 由同一疾病引起（如：感冒同时出现发热、咳嗽、乏力）\n"
        symptoms_info += "2. 由多种不同疾病分别引起（如：头痛和脚气可能无关）\n"
        symptoms_info += "3. 存在因果关系（如：失眠导致焦虑）\n"
        symptoms_info += "请分别针对每个症状进行鉴别诊断，并分析症状间的关联性。\n"
    
    # 如果是急危重症，直接返回紧急处理建议
    if is_emergency:
        return {
            "symptom_analysis": "患者存在危急症状：{}".format(emergency_type),
            "is_emergency": True,
            "emergency_type": emergency_type,
            "emergency_warning": emergency_desc,
            "risk_stratification": "急诊/立即转诊",
            "emergency_action": "请立即前往急诊或拨打120急救电话",
            "differential_diagnoses": [],
            "first_round_questions": [],
            "reasoning_chain": "根据症状分析，患者存在{}，属于急危重症范畴，需立即转诊急诊处理，不适合继续追问".format(emergency_type),
            "required_examinations": [],
            "optional_examinations": [],
            "disclaimer": "本系统仅提供辅助诊断参考，不替代面诊，需立即就医"
        }
    
    # 构建LLM提示词
    prompt = """{}{}

请根据上述患者信息，进行循证医学临床思维链分析：

【临床思维路径 - 必须严格遵循】

一、老年患者(>65岁)特殊考虑
1. 症状不典型：发热可能是感染的唯一表现
2. 多病共存：注意高血压、糖尿病、心血管疾病的多重影响
3. 用药复杂：注意药物副作用和相互作用
4. 机能下降：注意跌倒、失能风险

二、症状分析顺序
1. 首先识别危及生命的症状（红旗征）
2. 分析症状持续时间：急性(<2周)、亚急性(2周-3月)、慢性(>3月)
3. 分析症状严重程度：1-2级轻，3级中，4-5级重
4. 分析症状间的时间关系和因果关系

三、鉴别诊断原则
1. 优先考虑常见病、多发病
2. 排除危险疾病（肿瘤、感染、免疫病）
3. 考虑"一元论"：尽量用同一疾病解释多个症状
4. 注意老年患者的非典型表现

【分析步骤】

【第一步：症状收集与分析】
- 分析主要症状的特征、持续时间、严重程度
- 识别阳性症状和阴性症状

【第二步：诱因与既往史梳理】
- 分析与症状相关的诱因
- 结合既往病史、家族史、过敏史

【第三步：鉴别诊断】
- 如果是单个症状：列出可能的鉴别诊断（至少4个，按可能性排序）
- 如果是多症状：分别列出每个症状对应的鉴别诊断，并分析症状间关联
- 每个诊断需说明针对哪个症状，给出初始置信度（15-35%）
- 引用相关指南或教材作为依据
- 注意：同一疾病可能解释多个症状，需综合考虑

【第四步：辅助检查建议】
- 区分「必查项目」（明确诊断必需）
- 区分「可选/进阶项目」（进一步明确病情）

【第五步：初步诊断方向 - 重要约束】
- 判断是否需要继续追问以明确诊断
- 设计第一轮追问问题（必须恰好3-4个选择题！）
- 【强制要求】所有问题必须使用选择题形式：
  - input_type只能是：yesno（是否）、single（单选）、multiple（复选）
  - 禁止使用text类型！
  - 每个问题必须有3-5个选项
  - 例如："您发热时体温最高多少度？（单选）A.37-38℃ B.38-39℃ C.39-40℃ D.40℃以上"

- 问题应覆盖不同的症状，每个问题需明确针对哪个症状

请严格按照以下JSON格式输出：
```json
{
  "symptom_analysis": "对各症状特征、持续时间、严重程度的综合分析，包括症状间关联性",
  "is_emergency": false,
  "risk_stratification": "轻/中/重/急诊转诊",
  "symptom_diagnosis_mapping": {
    "症状名称": ["可能的诊断1", "可能的诊断2"]
  },
  "differential_diagnoses": [
    {
      "disease": "疾病名称",
      "confidence": 初始置信度,
      "reasoning": "为什么考虑这个诊断，引用循证依据",
      "category": "疾病分类",
      "related_symptoms": ["此诊断对应的症状"],
      "evidence_source": "依据来源（如：内科学、临床路径等）"
    }
  ],
  "required_examinations": [
    {"name": "检查项目名称", "purpose": "检查目的", "reason": "为什么必须做"}
  ],
  "optional_examinations": [
    {"name": "检查项目名称", "purpose": "检查目的", "reason": "可选原因"}
  ],
  "first_round_questions": [
    {
      "question_id": "q1",
      "question": "问题内容（必须是选择题，可以直接点击回答）",
      "input_type": "yesno/single/multiple",
      "options": ["选项A", "选项B", "选项C", "选项D"]（必须有3-5个选项）,
      "target_symptom": "这个问题针对的症状",
      "target_disease": "这个问题主要针对的诊断",
      "purpose": "这个问题想要明确什么"
    },
    {
      "question_id": "q2",
      "question": "问题内容（必须是选择题）",
      "input_type": "yesno/single/multiple",
      "options": ["选项A", "选项B", "选项C"]（必须有3-5个选项）,
      "target_symptom": "这个问题针对的症状",
      "target_disease": "这个问题主要针对的诊断",
      "purpose": "这个问题想要明确什么"
    },
    {
      "question_id": "q3",
      "question": "问题内容（必须是选择题）",
      "input_type": "yesno/single/multiple",
      "options": ["选项A", "选项B"]（至少2个选项）,
      "target_symptom": "这个问题针对的症状",
      "target_disease": "这个问题主要针对的诊断",
      "purpose": "这个问题想要明确什么"
    }
  ],
  "reasoning_chain": "循证医学临床思维链推理过程"
}
```

【强制要求】
- first_round_questions必须恰好包含3个或4个问题
- 每个问题必须包含question_id、question、input_type、target_disease字段
- input_type必须为yesno/single/multiple/text之一
- single和multiple类型必须提供options数组
- 问题要专业、具体，能够获取关键诊断信息
"""

    prompt = patient_info + symptoms_info + prompt

    try:
        result = await call_deepseek(prompt, system_prompt=EVIDENCE_BASED_SYSTEM_PROMPT, max_tokens=3000)
        
        # 解析JSON结果
        json_start = result.find('{')
        json_end = result.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            diagnosis_data = json.loads(result[json_start:json_end])
            # 确保is_emergency字段存在
            if 'is_emergency' not in diagnosis_data:
                diagnosis_data['is_emergency'] = False
            return diagnosis_data
        else:
            print("LLM返回结果无法解析: {}".format(result[:200]))
            raise ValueError("无法解析LLM返回的诊断结果")
    except Exception as e:
        print("生成初始诊断失败: {}".format(e))
        import traceback
        traceback.print_exc()
        return {
            "symptom_analysis": "基于症状特征的初步分析",
            "is_emergency": False,
            "risk_stratification": "待评估",
            "differential_diagnoses": [],
            "required_examinations": [],
            "optional_examinations": [],
            "first_round_questions": [],
            "reasoning_chain": "需要进一步问诊明确诊断",
            "disclaimer": "本诊断仅供参考，请咨询执业医师"
        }

def _generate_fallback_questions(session: DiagnosisSession, current_round: int) -> List[Dict]:
    """生成备用问题 - 当LLM调用失败时使用"""
    
    # 获取当前诊断假设
    symptoms = [s.description for s in session.symptoms]
    symptom = symptoms[0] if symptoms else "症状"
    
    # 基于症状生成基本问题
    fallback_questions = [
        {
            "question_id": f"q_fb_{current_round}_1",
            "question": f"您{symptom}的症状是否有加重或缓解的因素？（单选）",
            "input_type": "single",
            "options": ["有加重因素", "有缓解因素", "无明显变化", "不确定"],
            "target_symptom": symptom,
            "target_disease": "待明确",
            "purpose": "了解症状变化规律"
        },
        {
            "question_id": f"q_fb_{current_round}_2",
            "question": "您是否伴有其他不适症状？（复选）",
            "input_type": "multiple",
            "options": ["无其他症状", "发热", "乏力", "食欲下降", "体重变化", "睡眠问题"],
            "target_symptom": symptom,
            "target_disease": "待明确",
            "purpose": "收集伴随症状信息"
        },
        {
            "question_id": f"q_fb_{current_round}_3",
            "question": "您近期是否服用过新的药物或补充剂？（单选）",
            "input_type": "single",
            "options": ["是（新药物）", "是（补充剂）", "无", "不确定"],
            "target_symptom": symptom,
            "target_disease": "药物副作用待排除",
            "purpose": "排除药物相关因素"
        }
    ]
    
    return fallback_questions

async def generate_follow_up_questions(
    session: DiagnosisSession,
    new_answers: List[FollowUpAnswer]
) -> Dict:
    """使用LLM生成后续追问问题"""
    
    session.round_count += 1
    current_round = session.round_count
    
    # 更新回答记录
    for answer in new_answers:
        session.all_answers.append({
            "round": current_round,
            "question_id": answer.question_id,
            "question": answer.question,
            "answer": answer.answer,
            "answer_type": answer.answer_type
        })
    
    # 构建上下文
    answers_summary = "\n".join([
        "- {} → {}".format(a['question'], a['answer']) 
        for a in session.all_answers
    ])
    
    # 当前诊断假设
    hypothesis_summary = "\n".join([
        "- {}（置信度：{}%）：{}".format(d['disease'], d['confidence'], d.get('reasoning', '')[:50])
        for d in session.diagnosis_hypothesis[:4]
    ])
    
    # 构建患者信息
    gender_text = get_gender_text(session.patient_info.gender)
    patient_info_text = "{}岁{}".format(session.patient_info.age or '未填写', gender_text)
    
    # 追问系统提示词
    follow_up_system_prompt = EVIDENCE_BASED_SYSTEM_PROMPT + """

【临床思维链追问策略 - 必须严格遵循】

一、症状-诊断关联分析
1. 每回答一个患者回答，必须明确：这个回答支持哪些诊断？排除哪些诊断？
2. 不能孤立地看待每个症状，必须分析症状间的因果关系
3. 对于老年患者(>65岁)，必须考虑：不典型临床表现、多病共存、用药复杂性

二、问题设计原则（每轮3-4个）
1. 第一问：针对上一轮回答中最高置信度的诊断
2. 第二问：针对需要排除的危险疾病（红旗征）
3. 第三问：针对症状间的关联性
4. 第四问：针对鉴别诊断的特异性症状
5. 问题必须有逻辑递进关系，不能跳跃

三、置信度收敛规则（核心）
1. 每次调整必须有明确证据，变化幅度5-20%
2. 阳性体征/症状：+10-20%
3. 阴性体征/症状：-10-15%
4. 如果3个以上阳性指标指向同一诊断：+25-35%
5. 如果已有70%以上且继续升高，终止追问
6. 如果多个诊断置信度接近且差异<10%，增加鉴别问题

四、诊断明确条件（智能收敛）
- 主要诊断置信度≥70%，终止追问
- 或前两位诊断置信度差距≥30%，终止追问
- 或已完成4轮追问且诊断逐渐收敛，可终止追问
- 优先考虑诊断质量而非轮次数量

五、老年患者特殊考虑
- 症状不典型：发热可能是感染唯一表现
- 多病共存：高血压+动脉硬化+心衰可能同时存在
- 用药复杂：注意药物副作用和相互作用
- 机能下降：注意跌倒、失能风险

六、体征数据收集（关键）
在追问过程中，优先收集以下客观指标以提高诊断准确性：
1. 体温：是否发热（>37.3℃）
2. 心率：正常/过快（>100次/分）/过慢（<60次/分）
3. 血压：正常/升高/降低
4. 呼吸频率：正常/急促
5. 指尖血氧：正常（>95%）/偏低
6. 近期检查结果：血常规、尿常规、心电图、B超等

【重要】每轮问题中至少包含1-2个体征数据收集问题！
"""
    
    # 问题类型强制要求 - 避免文字输入
    # 注意：JSON示例中的大括号需要双写{{}}来转义
    json_template = '''请严格按照以下JSON格式输出：
```json
{{
  "diagnosis_updates": [
    {{
      "disease": "疾病名称",
      "confidence": 更新后的置信度,
      "confidence_change": "置信度变化原因（具体说明哪些回答支持或排除了该诊断）",
      "supporting_evidence": ["支持该诊断的具体证据"],
      "ruling_out_evidence": ["排除该诊断的具体证据"],
      "evidence_source": "依据来源"
    }}
  ],
  "is_diagnosis_clear": true/false,
  "risk_stratification": "轻/中/重/急诊转诊",
  "diagnosis_summary": "如果诊断已明确，给出简要总结",
  "next_round_questions": [
    {{
      "question_id": "q_rN_1",
      "question": "问题内容（必须是可以直接回答的选择题）",
      "input_type": "yesno/single/multiple",
      "options": ["选项A", "选项B", "选项C"]（必须有3-5个选项）,
      "target_symptom": "针对的症状",
      "target_disease": "针对的诊断",
      "purpose": "问题目的"
    }}
  ],
  "required_examinations": [{{"name": "项目", "purpose": "目的"}}],
  "optional_examinations": [{{"name": "项目", "purpose": "目的"}}],
  "reasoning_chain": "循证医学临床思维链的更新推理"
}}
```

【强制要求】
- next_round_questions必须恰好包含3个或4个问题
- 每个问题必须包含question_id、question、input_type、target_disease字段
- input_type必须为yesno/single/multiple/text之一
- single和multiple类型必须提供options数组'''
    
    prompt = f'''
【当前诊断会话上下文】

患者信息：{patient_info_text}
既往病史：{session.patient_info.history or '无'}

【已收集的症状】
{session.symptoms[0].description if session.symptoms else '无'}

【已完成的问诊回答】（共{current_round}轮）
{answers_summary}

【当前诊断假设】（按置信度排序）
{hypothesis_summary}

【当前轮次】：第{current_round}轮（共6轮）

【重要约束 - 必须遵守】
1. 所有问题必须使用选择题形式，禁止文字输入！
2. input_type只能是：yesno（是否）、single（单选）、multiple（复选）
3. 如果需要了解具体数值或描述，请转换为选项形式
4. 每轮必须生成恰好3-4个问题

例如：
- 不要问："您的心悸持续多久？"
- 改为问："您心悸发作时持续多长时间？（单选）A.几秒 B.几分钟 C.几小时 D.一整天"

请进行循证医学临床思维链分析：

1. 根据最新一轮回答，分析对各诊断置信度的影响，说明循证依据
2. 判断当前诊断是否已经足够明确
3. 如果需要继续追问，设计下一轮问题（3-4个选择题，必须是3-4个）

{json_template}

请生成下一轮的诊断更新和问题。
'''

    try:
        result = await call_deepseek(prompt, system_prompt=follow_up_system_prompt, max_tokens=3000)
        
        print(f"[DEBUG] LLM原始返回长度: {len(result)}")
        print(f"[DEBUG] LLM原始返回前500字符: {result[:500]}")
        
        # 解析JSON - 改进的解析逻辑
        json_start = result.find('{')
        json_end = result.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = result[json_start:json_end]
            print(f"[DEBUG] 提取的JSON字符串前300字符: {json_str[:300]}...")
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as je:
                print(f"[ERROR] JSON解析失败: {str(je)}")
                print(f"[ERROR] 尝试修复JSON...")
                
                # 尝试修复常见的JSON格式问题
                # 1. 移除可能存在的markdown代码块标记
                json_str = json_str.replace('```json', '').replace('```', '')
                
                # 2. 尝试修复尾部逗号等问题
                json_str = json_str.replace(',}', '}').replace(',]', ']')
                
                try:
                    return json.loads(json_str)
                except:
                    # 3. 尝试用正则提取主要字段
                    print(f"[ERROR] 修复失败，尝试提取关键字段...")
                    # 返回一个基本的默认结构
                    return {
                        "diagnosis_updates": [],
                        "is_diagnosis_clear": False,
                        "risk_stratification": "待评估",
                        "next_round_questions": _generate_fallback_questions(session, current_round),
                        "required_examinations": [],
                        "optional_examinations": [],
                        "reasoning_chain": "需要继续收集信息",
                        "error_detail": f"JSON解析失败，已启用备用问题集"
                    }
        else:
            print("无法解析LLM返回: {}".format(result[:200]))
            # 返回备用问题
            return {
                "diagnosis_updates": [],
                "is_diagnosis_clear": False,
                "risk_stratification": "待评估",
                "next_round_questions": _generate_fallback_questions(session, current_round),
                "required_examinations": [],
                "optional_examinations": [],
                "reasoning_chain": "需要继续收集信息"
            }
    except Exception as e:
        print("生成追问问题失败: {}".format(e))
        import traceback
        traceback.print_exc()
        return {
            "diagnosis_updates": [],
            "is_diagnosis_clear": False,
            "risk_stratification": "待评估",
            "next_round_questions": _generate_fallback_questions(session, current_round),
            "required_examinations": [],
            "optional_examinations": [],
            "reasoning_chain": "需要继续收集信息",
            "error_detail": str(e)
        }

async def generate_final_diagnosis(session: DiagnosisSession) -> Dict:
    """生成最终诊断报告"""
    
    # 构建完整的诊断上下文
    answers_detail = "\n".join([
        "第{}轮 - {} → {}".format(a['round'], a['question'], a['answer'])
        for a in session.all_answers
    ])
    
    # 构建患者信息
    gender_text = get_gender_text(session.patient_info.gender)
    patient_info_text = "{}岁{}".format(session.patient_info.age or '未填写', gender_text)
    
    # 最终诊断系统提示词
    final_system_prompt = EVIDENCE_BASED_SYSTEM_PROMPT + """

【最终诊断报告要求】
1. 主要诊断：置信度≥50%的诊断，按置信度排序，最多3个
2. 共病诊断/次要诊断：置信度30-50%的诊断
3. 每个诊断需给出详细推理过程和循证依据
4. 诊断依据需具体、可查证到具体文献
5. 参考文献需包含具体指南名称、章节、发表年份
6. 区分「必查项目」和「可选/进阶项目」
7. 明确风险分层和就医建议
"""
    
    prompt = """
【最终诊断请求】

患者信息：{}
既往病史：{}
过敏史：{}

【症状描述】
{}

【完整问诊记录】（共{}轮）
{}

【诊断假设演变过程】
{}

请生成最终诊断报告：

1. 主要诊断（置信度≥50%的诊断，按置信度排序，最多3个）
2. 共病诊断/次要诊断（置信度30-50%的诊断）
3. 每个诊断的详细推理过程（引用循证依据）
4. 每个诊断的具体诊断依据（阳性症状、检查结果等）
5. 参考文献/指南引用（必须包含具体指南名称和循证依据）
6. 区分「必查项目」和「可选/进阶项目」
7. 明确风险分层
8. 就医建议

请严格按照以下JSON格式输出：
```json
{
  "diagnoses": [
    {
      "disease": "疾病名称",
      "confidence": 置信度,
      "diagnosis_type": "主要诊断/共病可能",
      "reasoning": "详细的推理过程，包括症状分析、鉴别诊断、置信度调整原因",
      "evidence": ["具体证据1", "证据2"],
      "evidence_source": ["依据1（指南/教材名称）", "依据2"],
      "references": [
        {
          "title": "指南/文献名称（如：中国高血压防治指南2018）",
          "content": "相关的具体段落，需包含关键循证依据"
        }
      ],
      "suggestions": ["建议1：具体检查", "建议2：注意事项"]
    }
  ],
  "required_examinations": [
    {"name": "检查项目", "purpose": "目的", "reason": "为什么必须做"}
  ],
  "optional_examinations": [
    {"name": "检查项目", "purpose": "目的", "reason": "可选原因"}
  ],
  "risk_stratification": "轻/中/重/需急诊",
  "clinical_reasoning": "整体循证医学临床思维链总结",
  "disclaimer": "本诊断仅供参考，不替代面诊，请务必咨询执业医师"
}
```

注意：
- 置信度四舍五入到整数
- 每个诊断至少包含2条证据
- 参考文献必须有具体内容，不能只写标题
- 如需急诊，需明确标注
"""
    
    # 使用f-string替代format()避免JSON大括号冲突
    symptoms_desc = session.symptoms[0].description if session.symptoms else '无'
    
    prompt = f"""
【最终诊断请求】

患者信息：{patient_info_text}
既往病史：{session.patient_info.history or '无'}
过敏史：{session.patient_info.allergies or '无'}

【症状描述】
{symptoms_desc}

【完整问诊记录】（共{len(session.all_answers)}轮）
{answers_detail}

【诊断假设演变过程】
{json.dumps(session.diagnosis_hypothesis, ensure_ascii=False, indent=2)}

请生成最终诊断报告（严格按照JSON格式输出）：
```json
{{
  "diagnoses": [
    {{
      "disease": "疾病名称",
      "confidence": 置信度,
      "diagnosis_type": "主要诊断/共病可能",
      "reasoning": "详细推理过程",
      "evidence": ["证据1", "证据2"],
      "evidence_source": ["依据来源"],
      "references": [{{"title": "指南", "content": "相关内容"}}],
      "suggestions": ["建议"]
    }}
  ],
  "required_examinations": [{{"name": "项目", "purpose": "目的"}}],
  "optional_examinations": [{{"name": "项目", "purpose": "目的"}}],
  "risk_stratification": "轻/中/重/需急诊",
  "clinical_reasoning": "临床思维总结",
  "disclaimer": "仅供参考"
}}
```
"""

    try:
        result = await call_deepseek(prompt, system_prompt=final_system_prompt, max_tokens=3500)
        
        # 解析JSON
        json_start = result.find('{')
        json_end = result.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(result[json_start:json_end])
        else:
            raise ValueError("无法解析LLM返回的最终诊断")
    except Exception as e:
        print("生成最终诊断失败: {}".format(e))
        import traceback
        traceback.print_exc()
        return {
            "diagnoses": [],
            "required_examinations": [],
            "optional_examinations": [],
            "risk_stratification": "待评估",
            "clinical_reasoning": "诊断过程完成",
            "disclaimer": "本诊断仅供参考，请咨询执业医师"
        }

# ==================== API路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "全科医生辅助诊断系统",
        "version": "3.0.0",
        "description": "循证医学临床思维链辅助诊断",
        "status": "running",
        "principles": [
            "症状收集→鉴别诊断→辅助检查→初步确诊",
            "引用国家卫健委临床路径、《内科学》、WHO规范",
            "急危重症优先标注急诊/立即转诊"
        ]
    }

@app.post("/api/diagnosis/start")
async def start_diagnosis(request: DiagnosisRequest):
    """开始诊断流程"""
    
    # 创建新会话
    session_id = str(uuid.uuid4())
    session = DiagnosisSession(session_id)
    session.patient_info = request.patient
    session.symptoms = request.symptoms
    sessions[session_id] = session
    
    # 检查急危重症
    is_emergency, emergency_type, emergency_desc = check_emergency(request.symptoms)
    session.is_emergency = is_emergency
    session.emergency_type = emergency_type
    
    try:
        # 生成初始诊断
        diagnosis_data = await generate_initial_diagnosis(request)
        
        # 更新会话
        session.diagnosis_hypothesis = diagnosis_data.get('differential_diagnoses', [])
        session.current_questions = diagnosis_data.get('first_round_questions', [])
        
        # 合并返回数据
        return {
            "session_id": session_id,
            "symptom_analysis": diagnosis_data.get('symptom_analysis', ''),
            "is_emergency": diagnosis_data.get('is_emergency', is_emergency),
            "emergency_type": diagnosis_data.get('emergency_type', emergency_type),
            "emergency_warning": diagnosis_data.get('emergency_warning', emergency_desc),
            "risk_stratification": diagnosis_data.get('risk_stratification', '待评估'),
            "differential_diagnoses": session.diagnosis_hypothesis,
            "current_questions": session.current_questions,
            "reasoning_chain": diagnosis_data.get('reasoning_chain', ''),
            "required_examinations": diagnosis_data.get('required_examinations', []),
            "optional_examinations": diagnosis_data.get('optional_examinations', []),
            "is_diagnosis_clear": False,
            "disclaimer": diagnosis_data.get('disclaimer', '本诊断仅供参考，请咨询执业医师')
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/diagnosis/follow-up")
async def follow_up_diagnosis(request: FollowUpRequest):
    """继续追问流程"""
    
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在: {}".format(request.session_id))
    
    # 如果已经是急危重症，不继续追问
    if session.is_emergency:
        return {
            "session_id": session.session_id,
            "is_emergency": True,
            "emergency_type": session.emergency_type,
            "is_diagnosis_clear": True,
            "next_round_questions": [],
            "reasoning_chain": "患者存在急危重症，已标注转诊建议，不再继续追问"
        }
    
    try:
        # 生成后续问题
        result = await generate_follow_up_questions(session, request.answers)
        
        # 调试日志
        print(f"[DEBUG] generate_follow_up_questions 返回类型: {type(result)}")
        print(f"[DEBUG] generate_follow_up_questions 返回内容: {str(result)[:500]}")
        
        # 确保result是有效字典 - 添加安全检查
        if not isinstance(result, dict):
            print(f"[ERROR] result不是字典，而是: {type(result)}, 内容: {str(result)[:200]}")
            result = {
                "next_round_questions": _generate_fallback_questions(session, session.round_count), 
                "is_diagnosis_clear": False, 
                "reasoning_chain": "AI返回格式错误，已启用备用问题",
                "diagnosis_updates": [],
                "risk_stratification": "待评估"
            }
        
        # 安全地访问字典内容
        try:
            diagnosis_updates = result.get('diagnosis_updates', [])
            if diagnosis_updates and isinstance(diagnosis_updates, list):
                for update in diagnosis_updates:
                    for hyp in session.diagnosis_hypothesis:
                        if hyp.get('disease') == update.get('disease'):
                            hyp['confidence'] = update.get('confidence', hyp.get('confidence', 0))
                            hyp['reasoning'] = update.get('confidence_change', hyp.get('reasoning', ''))
                            break
        except Exception as update_err:
            print(f"[WARNING] 更新诊断假设失败: {update_err}")
        
        # 安全地获取返回值 - 使用get方法并提供默认值
        try:
            is_clear = result.get('is_diagnosis_clear', False) if isinstance(result, dict) else False
            next_questions = result.get('next_round_questions', []) if isinstance(result, dict) else []
        except Exception as get_err:
            print(f"[WARNING] 获取结果字段失败: {get_err}")
            is_clear = False
            next_questions = []
        
        # 如果诊断未明确但已达到最大轮次，也结束（智能收敛：4轮）
        if session.round_count >= 4 and not is_clear:
            is_clear = True
        
        session.is_diagnosis_clear = is_clear
        
        # 安全地构建返回字典
        try:
            diagnosis_updates = result.get('diagnosis_updates', []) if isinstance(result, dict) else []
            risk_strat = result.get('risk_stratification', '待评估') if isinstance(result, dict) else '待评估'
            diagnosis_summary = result.get('diagnosis_summary', '') if isinstance(result, dict) else ''
            reasoning_chain = result.get('reasoning_chain', '需要继续收集信息') if isinstance(result, dict) else '需要继续收集信息'
            required_exams = result.get('required_examinations', []) if isinstance(result, dict) else []
            optional_exams = result.get('optional_examinations', []) if isinstance(result, dict) else []
        except Exception as build_err:
            print(f"[WARNING] 构建返回数据失败: {build_err}")
            diagnosis_updates = []
            risk_strat = '待评估'
            diagnosis_summary = ''
            reasoning_chain = '需要继续收集信息'
            required_exams = []
            optional_exams = []
        
        return {
            "session_id": session.session_id,
            "diagnosis_updates": diagnosis_updates,
            "is_diagnosis_clear": is_clear,
            "risk_stratification": risk_strat,
            "diagnosis_summary": diagnosis_summary,
            "next_round_questions": next_questions if not is_clear else [],
            "reasoning_chain": reasoning_chain,
            "current_diagnoses": session.diagnosis_hypothesis,
            "required_examinations": required_exams,
            "optional_examinations": optional_exams,
            "round_count": session.round_count
        }
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] 追问接口异常: {str(e)}")
        print(f"[ERROR] 详细堆栈: {error_trace}")
        raise HTTPException(status_code=500, detail="追问处理失败: {}".format(str(e)))

@app.post("/api/diagnosis/final")
async def final_diagnosis(request: FollowUpRequest):
    """获取最终诊断报告"""
    
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    try:
        # 合并最后一轮答案
        for answer in request.answers:
            if not any(a['question_id'] == answer.question_id for a in session.all_answers):
                session.all_answers.append({
                    "round": session.round_count + 1,
                    "question_id": answer.question_id,
                    "question": answer.question,
                    "answer": answer.answer,
                    "answer_type": answer.answer_type
                })
        
        # 生成最终诊断
        diagnosis_report = await generate_final_diagnosis(session)
        
        return diagnosis_report
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 启动入口 ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
