"""
全科医生辅助诊断系统 - 后端服务
基于DeepSeek API实现循证医学临床思维链辅助诊断
遵循：国家卫健委全科医学临床路径、《内科学》教材、WHO诊疗规范
"""

import os
import json
import asyncio
import uuid
import re
import time
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
def _parse_cors_origins() -> List[str]:
    origins = os.getenv("CORS_ORIGINS", "*").strip()
    if not origins or origins == "*":
        return ["*"]
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


CORS_ORIGINS = _parse_cors_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_TIMEOUT_SECONDS = float(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "90"))
DEEPSEEK_MAX_RETRIES = int(os.getenv("DEEPSEEK_MAX_RETRIES", "2"))
LLM_DEBUG = os.getenv("LLM_DEBUG", "false").lower() == "true"
FAST_INITIAL_RESPONSE = os.getenv("FAST_INITIAL_RESPONSE", "true").lower() == "true"
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60 * 2)))
PLACEHOLDER_API_KEYS = {"", "your-deepseek-api-key-here", "your_deepseek_api_key_here"}

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

RED_FLAG_PATTERNS = {
    "急性冠脉综合征/主动脉夹层等胸痛急症": ["胸痛", "胸闷压榨", "胸口压榨", "大汗", "濒死感", "肩背放射痛"],
    "急性呼吸循环风险": ["呼吸困难", "喘不过气", "气促", "口唇发紫", "血氧低", "不能平卧"],
    "急性脑卒中风险": ["一侧无力", "肢体无力", "口角歪斜", "言语不清", "说话含糊", "视物双影", "偏瘫"],
    "颅内出血/脑膜刺激风险": ["剧烈头痛", "爆炸样头痛", "最严重头痛", "颈项强直", "喷射性呕吐"],
    "休克/严重感染风险": ["休克", "意识障碍", "昏迷", "高热惊厥", "大出血", "皮肤湿冷"],
}

NEGATIVE_WORDS = ["无", "没有", "否认", "未出现", "不伴", "无明显"]
HYPERTENSION_BP_RE = re.compile(r"(\d{2,3})\s*/\s*(\d{2,3})")
HYPERTENSION_REQUIRED_FACTS = {
    "blood_pressure_value": "血压数值",
    "measurement_context": "测量次数/测量条件",
    "hypertension_history": "既往高血压诊断史",
    "medication_status": "降压药使用情况",
    "red_flags_checked": "胸痛、呼吸困难、神经功能缺损等红旗征",
}

GENERAL_REQUIRED_FACTS = {
    "onset_duration": "起病时间/持续时间",
    "severity": "严重程度",
    "associated_symptoms": "伴随症状",
    "triggers_relief": "诱因/缓解因素",
    "medical_history": "既往史/用药史/过敏史",
    "red_flags_checked": "急危重症红旗征",
}

CLINICAL_PROFILES = {
    "hypertension": {
        "label": "血压升高/心血管风险",
        "system": "心血管系统",
        "keywords": ["高血压", "血压", "降压", "头晕", "头胀", "心悸"],
        "required_facts": HYPERTENSION_REQUIRED_FACTS,
        "must_not_miss": ["高血压急症", "急性冠脉综合征", "脑卒中", "主动脉夹层", "继发性高血压"],
        "baseline_differentials": ["原发性高血压", "继发性高血压", "高血压急症", "焦虑/睡眠问题相关血压波动"],
    },
    "fever_infection": {
        "label": "发热/感染待查",
        "system": "感染/呼吸/全身",
        "keywords": ["发热", "发烧", "高热", "寒战", "咳嗽", "咽痛", "流涕"],
        "must_not_miss": ["脓毒症", "肺炎", "脑膜炎", "急性肾盂肾炎"],
        "baseline_differentials": ["上呼吸道感染", "流感/新冠等病毒感染", "肺炎", "泌尿系感染", "非感染性发热"],
    },
    "fatigue_systemic": {
        "label": "乏力/全身症状",
        "system": "全身/内分泌/血液系统",
        "keywords": ["乏力", "疲乏", "疲劳", "没力气", "倦怠"],
        "must_not_miss": ["贫血", "甲状腺功能异常", "糖尿病", "慢性感染", "肿瘤相关消耗"],
        "baseline_differentials": ["睡眠不足/压力相关疲劳", "贫血", "甲状腺功能异常", "糖尿病或代谢异常", "慢性感染或炎症"],
    },
    "palpitation_cardio": {
        "label": "心悸/心律相关症状",
        "system": "心血管/内分泌系统",
        "keywords": ["心悸", "心慌", "心跳快", "心跳重", "心律不齐", "早搏"],
        "must_not_miss": ["严重心律失常", "急性冠脉综合征", "甲状腺功能亢进", "低钾等电解质紊乱"],
        "baseline_differentials": ["窦性心动过速", "早搏/阵发性心律失常", "焦虑或睡眠不足相关心悸", "甲状腺功能亢进", "贫血/低血糖"],
    },
    "chest_pain": {
        "label": "胸痛/胸闷",
        "system": "心血管/呼吸系统",
        "keywords": ["胸痛", "胸闷", "心前区", "胸口", "大汗", "肩背痛"],
        "must_not_miss": ["急性冠脉综合征", "主动脉夹层", "肺栓塞", "气胸"],
        "baseline_differentials": ["心绞痛/急性冠脉综合征", "胃食管反流", "肋软骨炎", "焦虑发作", "肺部疾病"],
    },
    "abdominal_pain": {
        "label": "腹痛/消化道症状",
        "system": "消化系统",
        "keywords": ["腹痛", "肚子痛", "胃痛", "恶心", "呕吐", "腹泻", "便秘", "黑便", "腹胀", "返酸", "反酸", "烧心", "嗳气"],
        "must_not_miss": ["急腹症", "消化道出血", "胰腺炎", "胆囊炎", "肠梗阻"],
        "baseline_differentials": ["急性胃肠炎", "功能性消化不良", "胃食管反流病", "胆囊/胆道疾病", "阑尾炎", "胃十二指肠疾病"],
    },
    "headache_dizziness": {
        "label": "头痛/头晕",
        "system": "神经/心血管系统",
        "keywords": ["头痛", "头疼", "头晕", "眩晕", "头昏", "眼花"],
        "must_not_miss": ["脑卒中", "颅内出血", "脑膜炎", "高血压急症"],
        "baseline_differentials": ["紧张型头痛", "偏头痛", "良性阵发性位置性眩晕", "周围神经病变", "血压异常", "贫血/低血糖"],
    },
    "neuro_sensory_ent": {
        "label": "麻木/耳鸣/感觉异常",
        "system": "神经/耳鼻喉系统",
        "keywords": ["麻木", "刺痛", "感觉异常", "耳鸣", "听力下降", "耳闷"],
        "must_not_miss": ["脑卒中", "突发性耳聋", "脊髓/神经根压迫", "糖尿病周围神经病变"],
        "baseline_differentials": ["周围神经病变", "颈椎/腰椎神经根病", "脑血管事件需排除", "耳源性疾病", "代谢或电解质异常"],
    },
    "edema_systemic": {
        "label": "水肿/容量负荷异常",
        "system": "肾脏/心血管/内分泌系统",
        "keywords": ["水肿", "浮肿", "眼睑肿", "脚肿", "下肢肿", "尿少", "泡沫尿"],
        "must_not_miss": ["心力衰竭", "肾病综合征", "急性肾损伤", "肝硬化失代偿", "严重低蛋白血症"],
        "baseline_differentials": ["肾脏疾病相关水肿", "心力衰竭相关水肿", "肝病/低蛋白血症", "甲状腺功能减退", "药物相关水肿"],
    },
    "weight_loss_systemic": {
        "label": "消瘦/体重下降",
        "system": "全身/内分泌/消化系统",
        "keywords": ["消瘦", "体重下降", "体重减轻", "食欲下降", "盗汗", "长期低热"],
        "must_not_miss": ["恶性肿瘤", "结核等慢性感染", "甲状腺功能亢进", "糖尿病", "消化吸收不良"],
        "baseline_differentials": ["摄入不足/营养不良", "甲状腺功能亢进", "糖尿病", "慢性感染", "肿瘤相关消耗"],
    },
    "skin_pruritus": {
        "label": "瘙痒/皮肤症状",
        "system": "皮肤/过敏/肝肾系统",
        "keywords": ["瘙痒", "皮痒", "皮疹", "荨麻疹", "红斑", "脱屑"],
        "must_not_miss": ["严重过敏反应", "胆汁淤积", "尿毒症相关瘙痒", "药疹"],
        "baseline_differentials": ["湿疹/皮炎", "荨麻疹", "真菌感染", "药物或食物过敏", "肝胆或肾功能异常相关瘙痒"],
    },
    "oral_thirst": {
        "label": "口干/口臭/口腔相关症状",
        "system": "口腔/消化/内分泌系统",
        "keywords": ["口干", "口臭", "口苦", "口腔溃疡", "多饮", "多尿"],
        "must_not_miss": ["糖尿病酮症风险", "干燥综合征", "口腔严重感染"],
        "baseline_differentials": ["口腔卫生或牙周疾病", "胃食管反流/消化不良", "糖尿病或血糖异常", "干燥综合征", "药物相关口干"],
    },
    "urinary": {
        "label": "泌尿系统症状",
        "system": "泌尿系统",
        "keywords": ["尿频", "尿急", "尿痛", "血尿", "腰痛", "排尿困难", "尿少"],
        "must_not_miss": ["急性肾盂肾炎", "尿路梗阻", "急性肾损伤"],
        "baseline_differentials": ["下尿路感染", "急性肾盂肾炎", "泌尿系结石", "前列腺相关疾病"],
    },
    "musculoskeletal": {
        "label": "肌骨疼痛/活动受限",
        "system": "肌肉骨骼系统",
        "keywords": ["腰痛", "背痛", "关节痛", "颈痛", "麻木", "活动受限", "扭伤"],
        "must_not_miss": ["骨折", "马尾综合征", "感染性关节炎", "肿瘤相关疼痛"],
        "baseline_differentials": ["肌肉劳损", "腰椎间盘突出", "骨关节炎", "颈椎病", "炎症性关节病"],
    },
    "mental_sleep": {
        "label": "心理/睡眠/躯体化症状",
        "system": "精神心理/睡眠",
        "keywords": ["焦虑", "失眠", "睡不着", "心慌", "胸闷", "疲劳", "压力", "乏力"],
        "must_not_miss": ["自伤自杀风险", "甲状腺功能异常", "心律失常", "物质/药物相关问题"],
        "baseline_differentials": ["焦虑状态", "失眠障碍", "躯体化症状", "甲状腺功能异常", "心律失常"],
    },
    "general": {
        "label": "未分化主诉",
        "system": "全科未分化疾病",
        "keywords": [],
        "must_not_miss": ["急危重症", "感染", "心脑血管事件", "肿瘤或系统性疾病"],
        "baseline_differentials": ["常见感染性疾病", "功能性/生活方式相关问题", "慢性病急性波动", "需进一步检查的器质性疾病"],
    },
}

CLINICAL_PROFILE_PRIORITY = [
    "hypertension",
    "palpitation_cardio",
    "chest_pain",
    "fever_infection",
    "fatigue_systemic",
    "abdominal_pain",
    "edema_systemic",
    "weight_loss_systemic",
    "skin_pruritus",
    "oral_thirst",
    "neuro_sensory_ent",
    "headache_dizziness",
    "musculoskeletal",
    "urinary",
    "mental_sleep",
    "general",
]

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
        self.clinical_state: Dict[str, Any] = {}

# 会话存储
sessions: Dict[str, DiagnosisSession] = {}

# ==================== 辅助函数 ====================
def has_valid_deepseek_key() -> bool:
    """检查是否配置了可用的DeepSeek API Key。"""
    return DEEPSEEK_API_KEY not in PLACEHOLDER_API_KEYS


def cleanup_expired_sessions() -> None:
    """清理过期内存会话，避免长期运行时持续占用内存。"""
    now = datetime.now()
    expired_session_ids = [
        session_id
        for session_id, session in sessions.items()
        if (now - session.created_at).total_seconds() > SESSION_TTL_SECONDS
    ]
    for session_id in expired_session_ids:
        sessions.pop(session_id, None)


def parse_llm_json_object(text: str) -> Dict[str, Any]:
    """从LLM返回文本中提取第一个有效JSON对象。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.replace("```json", "", 1).replace("```", "", 1).strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("无法解析LLM返回的JSON对象")


def _clip_text(value: Any, limit: int = 120) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，。；,; ") + "..."


def _clip_list(values: Any, max_items: int = 3, text_limit: int = 80) -> List[Any]:
    if not isinstance(values, list):
        return []
    clipped = []
    for item in values[:max_items]:
        if isinstance(item, dict):
            compact_item = dict(item)
            for key in ("purpose", "reason", "content", "title"):
                if key in compact_item:
                    compact_item[key] = _clip_text(compact_item[key], text_limit)
            clipped.append(compact_item)
        else:
            clipped.append(_clip_text(item, text_limit))
    return clipped


def compact_llm_output(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data

    for key, limit in (
        ("symptom_analysis", 160),
        ("reasoning_chain", 140),
        ("clinical_reasoning", 160),
        ("diagnosis_summary", 140),
    ):
        if key in data:
            data[key] = _clip_text(data[key], limit)

    for key in ("required_examinations", "optional_examinations"):
        if key in data:
            data[key] = _clip_list(data[key], 3, 90)

    for diag in data.get("differential_diagnoses", []) or []:
        if isinstance(diag, dict):
            diag["reasoning"] = _clip_text(diag.get("reasoning", ""), 90)
            diag["related_symptoms"] = _clip_list(diag.get("related_symptoms", []), 3, 40)

    for update in data.get("diagnosis_updates", []) or []:
        if isinstance(update, dict):
            update["confidence_change"] = _clip_text(update.get("confidence_change", ""), 90)
            update["supporting_evidence"] = _clip_list(update.get("supporting_evidence", []), 2, 70)
            update["ruling_out_evidence"] = _clip_list(update.get("ruling_out_evidence", []), 2, 70)

    for diag in data.get("diagnoses", []) or []:
        if isinstance(diag, dict):
            diag["reasoning"] = _clip_text(diag.get("reasoning", ""), 100)
            diag["evidence"] = _clip_list(diag.get("evidence", []), 3, 70)
            diag["evidence_source"] = _clip_list(diag.get("evidence_source", []), 2, 80)
            diag["references"] = _clip_list(diag.get("references", []), 2, 90)
            diag["suggestions"] = _clip_list(diag.get("suggestions", []), 3, 70)

    return data


def _stringify_answer(answer: Any) -> str:
    if isinstance(answer, list):
        return "、".join(str(item) for item in answer)
    return str(answer or "")


def _contains_negative_context(text: str, keyword: str) -> bool:
    index = text.find(keyword)
    if index < 0:
        return False
    window = text[max(0, index - 6): index + len(keyword) + 2]
    if any(word in window for word in NEGATIVE_WORDS):
        return True

    clause_start = max(text.rfind(mark, 0, index) for mark in ["，", "。", "；", ";", ".", "\n"])
    clause = text[clause_start + 1: index + len(keyword)]
    return any(word in clause[:8] for word in NEGATIVE_WORDS)


def _combined_case_text(patient: PatientInfo, symptoms: List[Symptom], answers: Optional[List[Dict[str, Any]]] = None) -> str:
    parts = [patient.history or "", patient.allergies or ""]
    parts.extend(symptom.description for symptom in symptoms)
    for answer in answers or []:
        parts.append(str(answer.get("question", "")))
        parts.append(_stringify_answer(answer.get("answer")))
    return "\n".join(parts)


def screen_red_flags(symptoms: List[Symptom], answers: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """结构化红旗征筛查，阴性表述不触发急诊分流。"""
    text = "\n".join([s.description for s in symptoms] + [
        "{} {}".format(a.get("question", ""), _stringify_answer(a.get("answer")))
        for a in answers or []
    ]).lower()
    matched = []
    for category, keywords in RED_FLAG_PATTERNS.items():
        for keyword in keywords:
            if keyword in text and not _contains_negative_context(text, keyword):
                matched.append({"category": category, "keyword": keyword})
                break

    return {
        "is_emergency": bool(matched),
        "matched_red_flags": matched,
        "recommended_action": "立即急诊/拨打120" if matched else "继续结构化问诊",
    }


def _extract_bp_values(text: str) -> List[Dict[str, int]]:
    values = []
    for systolic, diastolic in HYPERTENSION_BP_RE.findall(text):
        sys_value = int(systolic)
        dia_value = int(diastolic)
        if 70 <= sys_value <= 260 and 40 <= dia_value <= 160:
            values.append({"systolic": sys_value, "diastolic": dia_value})
    return values


def infer_case_focus(patient: PatientInfo, symptoms: List[Symptom], answers: Optional[List[Dict[str, Any]]] = None) -> str:
    text = _combined_case_text(patient, symptoms, answers)
    if any(word in text for word in ["高血压", "血压", "降压"]) or _extract_bp_values(text):
        return "hypertension"
    best_key = "general"
    best_score = 0
    for key in CLINICAL_PROFILE_PRIORITY:
        if key in {"hypertension", "general"}:
            continue
        profile = CLINICAL_PROFILES[key]
        score = sum(1 for word in profile.get("keywords", []) if word in text)
        if key == "musculoskeletal" and _has_any(text, ["久坐", "弯腰", "扭伤", "活动后", "颈肩", "放射痛"]):
            score += 2
        if key == "urinary" and _has_any(text, ["尿频", "尿急", "尿痛", "血尿", "排尿"]):
            score += 2
        if key == "abdominal_pain" and _has_any(text, ["进食", "饭后", "腹泻", "黑便", "呕吐"]):
            score += 2
        if score > best_score:
            best_key = key
            best_score = score
    return best_key


def _has_any(text: str, words: List[str]) -> bool:
    return any(word in text for word in words)


def _has_duration(symptoms: List[Symptom], text: str) -> bool:
    if any(s.duration_years or s.duration_months or s.duration_days for s in symptoms):
        return True
    return _has_any(text, ["天", "周", "月", "年", "小时", "分钟", "昨", "今", "最近", "长期", "反复", "突然"])


def _general_required_facts(text: str, symptoms: List[Symptom], patient: PatientInfo, red_flags: Dict[str, Any]) -> Dict[str, bool]:
    return {
        "onset_duration": _has_duration(symptoms, text),
        "severity": any(s.severity > 1 for s in symptoms) or _has_any(text, ["轻", "中", "重", "剧烈", "明显", "严重", "最高", "加重"]),
        "associated_symptoms": len(symptoms) > 1 or _has_any(text, ["伴", "同时", "合并", "没有", "无", "否认"]),
        "triggers_relief": _has_any(text, ["诱因", "劳累", "进食", "运动", "体位", "缓解", "加重", "夜间", "饭后", "受凉"]),
        "medical_history": bool(patient.history or patient.allergies) or _has_any(text, ["既往", "病史", "用药", "服药", "过敏", "家族"]),
        "red_flags_checked": bool(red_flags["matched_red_flags"]) or _has_any(text, ["胸痛", "呼吸困难", "意识", "一侧", "言语", "大出血", "剧烈", "无以下"]),
    }


def _specialized_required_facts(focus: str, text: str, symptoms: List[Symptom], patient: PatientInfo, red_flags: Dict[str, Any]) -> Dict[str, bool]:
    if focus == "hypertension":
        bp_values = _extract_bp_values(text)
        return {
            "blood_pressure_value": bool(bp_values),
            "measurement_context": _has_any(text, ["多次", "家庭", "自测", "诊室", "动态血压", "复测"]),
            "hypertension_history": "高血压" in text,
            "medication_status": _has_any(text, ["降压药", "服药", "未规律", "规律服", "药物"]),
            "red_flags_checked": _general_required_facts(text, symptoms, patient, red_flags)["red_flags_checked"],
        }
    return _general_required_facts(text, symptoms, patient, red_flags)


def build_clinical_state(
    patient: PatientInfo,
    symptoms: List[Symptom],
    answers: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """生成可审计的规则状态，作为LLM输出的边界。"""
    answers = answers or []
    text = _combined_case_text(patient, symptoms, answers)
    focus = infer_case_focus(patient, symptoms, answers)
    red_flags = screen_red_flags(symptoms, answers)
    bp_values = _extract_bp_values(text)

    profile = CLINICAL_PROFILES.get(focus, CLINICAL_PROFILES["general"])
    required_fact_labels = profile.get("required_facts", GENERAL_REQUIRED_FACTS)
    required_facts = _specialized_required_facts(focus, text, symptoms, patient, red_flags)
    missing_facts = [
        required_fact_labels.get(key, GENERAL_REQUIRED_FACTS.get(key, key))
        for key in required_fact_labels
        if not required_facts.get(key)
    ]

    return {
        "focus": focus,
        "profile_label": profile["label"],
        "system": profile["system"],
        "red_flags": red_flags,
        "bp_values": bp_values,
        "required_facts": required_facts,
        "missing_facts": missing_facts,
        "required_facts_complete": not missing_facts,
        "red_flags_checked": required_facts.get("red_flags_checked", bool(red_flags["matched_red_flags"])),
        "must_not_miss": profile.get("must_not_miss", []),
        "baseline_differentials": profile.get("baseline_differentials", []),
    }


def rule_based_diagnosis_scores(state: Dict[str, Any], patient: PatientInfo, symptoms: List[Symptom]) -> List[Dict[str, Any]]:
    """规则层只输出可解释评分，不冒充真实疾病概率。"""
    if state.get("focus") != "hypertension":
        text = _combined_case_text(patient, symptoms)
        baseline_differentials = list(state.get("baseline_differentials", []))
        if state.get("focus") == "abdominal_pain":
            if _has_any(text, ["返酸", "反酸", "烧心"]):
                baseline_differentials = ["胃食管反流病", "功能性消化不良", "胃十二指肠疾病", "胆囊/胆道疾病"]
            elif "腹胀" in text:
                baseline_differentials = ["功能性消化不良", "胃食管反流病", "肠易激综合征", "肠梗阻需排除"]
        elif state.get("focus") == "neuro_sensory_ent":
            if _has_any(text, ["耳鸣", "听力下降", "耳闷"]):
                baseline_differentials = ["耳源性疾病", "突发性耳聋需排除", "前庭系统疾病", "脑血管事件需排除"]
            elif _has_any(text, ["麻木", "刺痛", "感觉异常"]):
                baseline_differentials = ["周围神经病变", "颈椎/腰椎神经根病", "脑血管事件需排除", "代谢或电解质异常"]
        elif state.get("focus") == "headache_dizziness" and _has_any(text, ["头晕", "眩晕", "头昏"]):
            baseline_differentials = ["良性阵发性位置性眩晕", "血压异常", "贫血/低血糖", "脑血管事件需排除"]

        scores = []
        base_score = 35
        if state.get("required_facts_complete"):
            base_score += 10
        if len(symptoms) > 1:
            base_score += 5
        for disease in baseline_differentials[:4]:
            scores.append({
                "disease": disease,
                "evidence_score": base_score,
                "evidence": [
                    "主诉匹配{}入口".format(state.get("profile_label", "未分化主诉")),
                    "仍需结合问诊和必要检查进行鉴别",
                ],
                "role": "baseline_differential",
            })
        for disease in state.get("must_not_miss", [])[:3]:
            scores.append({
                "disease": "{}需排除".format(disease),
                "evidence_score": 25,
                "evidence": ["全科未分化疾病需优先排除危险诊断：{}".format(disease)],
                "role": "must_not_miss",
            })
        return scores

    text = _combined_case_text(patient, symptoms)
    bp_values = state.get("bp_values", [])
    max_systolic = max([bp["systolic"] for bp in bp_values], default=0)
    max_diastolic = max([bp["diastolic"] for bp in bp_values], default=0)

    hypertension_score = 20
    evidence = []
    if max_systolic >= 140 or max_diastolic >= 90:
        hypertension_score += 35
        evidence.append("记录到血压达到高血压阈值（≥140/90mmHg）")
    if "高血压" in text:
        hypertension_score += 15
        evidence.append("既往史或主诉中出现高血压相关信息")
    if any(word in text for word in ["头晕", "头胀", "头痛", "心悸"]):
        hypertension_score += 5
        evidence.append("存在头晕/头胀/心悸等常见伴随症状")
    if any(word in text for word in ["父亲", "母亲", "家族"]):
        hypertension_score += 5
        evidence.append("存在家族史线索")
    if any(word in text for word in ["未规律", "未服", "降压药"]):
        hypertension_score += 5
        evidence.append("存在降压治疗依从性或用药状态线索")

    osa_positive = any(word in text for word in ["打鼾", "憋醒", "呼吸暂停", "嗜睡"]) and not any(
        phrase in text for phrase in ["无打鼾", "无夜间憋醒", "没有打鼾", "否认打鼾"]
    )
    secondary_clues = any(word in text for word in ["肾病", "低钾", "阵发", "多汗", "肾动脉", "内分泌"])

    scores = [
        {
            "disease": "原发性高血压",
            "evidence_score": min(hypertension_score, 85),
            "evidence": evidence,
            "role": "likely_diagnosis",
        },
        {
            "disease": "继发性高血压需排除",
            "evidence_score": 35 if secondary_clues else 20,
            "evidence": ["高血压初评需排除肾脏、内分泌、药物等继发因素"] + (["存在继发性高血压线索"] if secondary_clues else []),
            "role": "differential_diagnosis",
        },
    ]
    if osa_positive:
        scores.append({
            "disease": "阻塞性睡眠呼吸暂停相关高血压可能",
            "evidence_score": 35,
            "evidence": ["存在打鼾、憋醒或呼吸暂停线索"],
            "role": "comorbidity_or_contributor",
        })
    return scores


def _question_key(question: Dict[str, Any]) -> str:
    return "{}|{}".format(question.get("question", ""), question.get("target_disease", ""))


def hypertension_required_questions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    missing = set(state.get("missing_facts", []))
    questions = []
    if "血压数值" in missing or "测量次数/测量条件" in missing:
        questions.append({
            "question_id": "rule_htn_bp",
            "question": "您最近血压最高大约是多少，且是在什么情况下测得？（单选）",
            "input_type": "single",
            "options": ["<140/90mmHg", "140-159/90-99mmHg，多次测得", "≥160/100mmHg，多次测得", "仅偶然一次偏高", "不清楚"],
            "target_symptom": "血压升高",
            "target_disease": "原发性高血压",
            "purpose": "确认客观血压水平与测量可靠性",
            "question_group": "core_fact",
        })
    if "既往高血压诊断史" in missing:
        questions.append({
            "question_id": "rule_htn_history",
            "question": "既往是否被医生诊断过高血压？（单选）",
            "input_type": "single",
            "options": ["已诊断高血压", "多次血压偏高但未确诊", "从未诊断", "不清楚"],
            "target_symptom": "血压升高",
            "target_disease": "原发性高血压",
            "purpose": "明确既往诊断状态",
            "question_group": "core_fact",
        })
    if "降压药使用情况" in missing:
        questions.append({
            "question_id": "rule_htn_medication",
            "question": "目前降压药使用情况如何？（单选）",
            "input_type": "single",
            "options": ["规律服用", "未规律服用", "从未服用", "近期自行停药", "不清楚"],
            "target_symptom": "血压升高",
            "target_disease": "血压控制情况",
            "purpose": "评估治疗依从性和血压控制原因",
            "question_group": "core_fact",
        })
    if "胸痛、呼吸困难、神经功能缺损等红旗征" in missing:
        questions.append({
            "question_id": "rule_red_flags",
            "question": "是否出现以下需要立即就医的情况？（复选）",
            "input_type": "multiple",
            "options": ["无以下情况", "胸痛/胸口压榨感", "呼吸困难", "一侧肢体无力或言语不清", "剧烈头痛或意识异常"],
            "target_symptom": "红旗征筛查",
            "target_disease": "急危重症排除",
            "purpose": "完成安全分流",
            "question_group": "red_flag",
        })
    return questions


def general_required_questions(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    missing = set(state.get("missing_facts", []))
    label = state.get("profile_label", "当前症状")
    questions = []
    if "起病时间/持续时间" in missing:
        questions.append({
            "question_id": "rule_general_onset",
            "question": "这次不适是从什么时候开始的？（单选）",
            "input_type": "single",
            "options": ["24小时内", "1-3天", "4-14天", "超过2周", "反复发作超过1个月"],
            "target_symptom": label,
            "target_disease": "病程判断",
            "purpose": "明确急性、亚急性或慢性病程",
            "question_group": "core_fact",
        })
    if "严重程度" in missing:
        questions.append({
            "question_id": "rule_general_severity",
            "question": "目前不适程度最接近哪一项？（单选）",
            "input_type": "single",
            "options": ["轻微，不影响活动", "中等，影响日常活动", "较重，需要休息", "非常严重/难以忍受"],
            "target_symptom": label,
            "target_disease": "风险分层",
            "purpose": "评估严重程度和就医优先级",
            "question_group": "core_fact",
        })
    if "伴随症状" in missing:
        questions.append({
            "question_id": "rule_general_associated",
            "question": "是否伴随以下情况？（复选）",
            "input_type": "multiple",
            "options": ["无明显伴随症状", "发热/寒战", "恶心呕吐/腹泻", "胸闷胸痛/气促", "头痛头晕/肢体麻木", "乏力或体重变化"],
            "target_symptom": label,
            "target_disease": "系统归属与鉴别诊断",
            "purpose": "建立症状组合，缩小鉴别范围",
            "question_group": "core_fact",
        })
    if "诱因/缓解因素" in missing:
        questions.append({
            "question_id": "rule_general_trigger",
            "question": "症状与哪些因素有关？（复选）",
            "input_type": "multiple",
            "options": ["无明显诱因", "劳累/运动", "进食/饮酒", "体位变化", "受凉或接触感染者", "休息或用药后缓解"],
            "target_symptom": label,
            "target_disease": "诱因分析",
            "purpose": "识别诱因、加重和缓解因素",
            "question_group": "core_fact",
        })
    if "既往史/用药史/过敏史" in missing:
        questions.append({
            "question_id": "rule_general_history",
            "question": "既往病史和近期用药情况如何？（复选）",
            "input_type": "multiple",
            "options": ["无特殊病史", "有慢性病", "近期使用新药/保健品", "有药物或食物过敏", "近期做过检查或治疗"],
            "target_symptom": label,
            "target_disease": "病史与药物相关问题",
            "purpose": "补齐既往史、用药史和过敏史",
            "question_group": "core_fact",
        })
    if "急危重症红旗征" in missing:
        questions.append({
            "question_id": "rule_general_red_flags",
            "question": "是否出现以下任一需要立即就医的情况？（复选）",
            "input_type": "multiple",
            "options": ["无以下情况", "胸痛/呼吸困难", "意识异常/昏迷", "一侧肢体无力或言语不清", "剧烈头痛/持续高热", "大出血或皮肤湿冷"],
            "target_symptom": "红旗征筛查",
            "target_disease": "急危重症排除",
            "purpose": "完成安全分流",
            "question_group": "red_flag",
        })
    return questions


def merge_guardrail_questions(state: Dict[str, Any], llm_questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    guardrail_questions = hypertension_required_questions(state) if state.get("focus") == "hypertension" else general_required_questions(state)
    merged = []
    seen = set()
    for question in guardrail_questions + (llm_questions or []):
        key = _question_key(question)
        if key in seen:
            continue
        seen.add(key)
        question.setdefault("question_group", "differential")
        merged.append(question)
    return merged[:4]


def ensure_minimum_questions(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    supplements = [
        {
            "question_id": "rule_fast_pattern",
            "question": "症状目前呈现怎样的变化趋势？（单选）",
            "input_type": "single",
            "options": ["逐渐加重", "基本稳定", "间断反复", "已有明显缓解"],
            "target_disease": "病程判断",
            "purpose": "判断病情进展速度和风险层级",
            "question_group": "core_fact",
        },
        {
            "question_id": "rule_fast_systemic",
            "question": "是否伴随以下全身情况？（复选）",
            "input_type": "multiple",
            "options": ["发热或寒战", "明显乏力", "体重下降", "夜间出汗", "均无"],
            "target_disease": "系统性疾病筛查",
            "purpose": "补充感染、肿瘤、内分泌或免疫性疾病线索",
            "question_group": "core_fact",
        },
        {
            "question_id": "rule_fast_red_flag",
            "question": "是否出现以下需要优先就医的情况？（复选）",
            "input_type": "multiple",
            "options": ["胸痛或胸闷明显", "呼吸困难", "意识异常或晕厥", "剧烈疼痛", "均无"],
            "target_disease": "红旗征筛查",
            "purpose": "排查需要急诊处理的危险信号",
            "question_group": "red_flag",
        },
    ]
    merged = list(questions or [])
    seen = {_question_key(q) for q in merged}
    for question in supplements:
        key = _question_key(question)
        if key not in seen:
            merged.append(question)
            seen.add(key)
        if len(merged) >= 3:
            break
    return merged[:4]


def build_fast_initial_diagnosis(
    state: Dict[str, Any],
    patient: PatientInfo,
    symptoms: List[Symptom],
) -> Dict[str, Any]:
    rule_scores = rule_based_diagnosis_scores(state, patient, symptoms)
    symptom_text = "；".join(
        "{}（{}，{}级）".format(
            s.description,
            get_duration_text(s.duration_years, s.duration_months, s.duration_days or 0),
            s.severity or 1,
        )
        for s in symptoms
    )
    diagnoses = []
    for score in rule_scores[:5]:
        diagnoses.append({
            "disease": score["disease"],
            "confidence": score["evidence_score"],
            "evidence_score": score["evidence_score"],
            "reasoning": "规则层提示：{}".format("；".join(score["evidence"])),
            "category": score["role"],
            "related_symptoms": [s.description for s in symptoms],
            "evidence_source": "结构化规则评分",
        })

    if not diagnoses:
        diagnoses = [{
            "disease": "未分化全科症状待鉴别",
            "confidence": 35,
            "evidence_score": 35,
            "reasoning": "当前信息不足，需先补齐起病时间、严重程度、伴随症状、诱因、既往病史和红旗征。",
            "category": "differential_diagnosis",
            "related_symptoms": [s.description for s in symptoms],
            "evidence_source": "全科未分化症状分诊规则",
        }]

    diagnosis_data = {
        "symptom_analysis": "已完成快速分诊：{}".format(symptom_text or "未填写明确症状"),
        "is_emergency": False,
        "risk_stratification": "待评估",
        "differential_diagnoses": diagnoses,
        "required_examinations": [],
        "optional_examinations": [],
        "first_round_questions": ensure_minimum_questions(merge_guardrail_questions(state, [])),
        "reasoning_chain": "快速首轮采用红旗征筛查、核心事实补齐和规则评分生成；后续追问和最终报告继续结合大模型细化鉴别诊断。",
        "rule_based_scores": rule_scores,
        "llm_deferred": True,
        "disclaimer": "本诊断仅供参考，请咨询执业医师",
    }
    return apply_initial_guardrails(diagnosis_data, state, patient, symptoms)


def apply_initial_guardrails(
    diagnosis_data: Dict[str, Any],
    state: Dict[str, Any],
    patient: PatientInfo,
    symptoms: List[Symptom],
) -> Dict[str, Any]:
    diagnosis_data["assessment_state"] = state
    diagnosis_data["red_flag_screening"] = state.get("red_flags", {})
    if state["red_flags"]["is_emergency"]:
        diagnosis_data.update({
            "is_emergency": True,
            "emergency_warning": "匹配红旗征：{}".format(
                "、".join(item["keyword"] for item in state["red_flags"]["matched_red_flags"])
            ),
            "risk_stratification": "急诊/立即转诊",
            "first_round_questions": [],
            "is_diagnosis_clear": True,
        })
        return diagnosis_data

    diagnosis_data["is_emergency"] = False
    diagnosis_data.pop("emergency_warning", None)

    rule_scores = rule_based_diagnosis_scores(state, patient, symptoms)
    if rule_scores:
        diagnosis_data["rule_based_scores"] = rule_scores
        existing = {d.get("disease"): d for d in diagnosis_data.get("differential_diagnoses", [])}
        for score in rule_scores:
            disease = score["disease"]
            if disease in existing:
                existing[disease]["evidence_score"] = score["evidence_score"]
                existing[disease]["rule_evidence"] = score["evidence"]
            else:
                diagnosis_data.setdefault("differential_diagnoses", []).append({
                    "disease": disease,
                    "confidence": score["evidence_score"],
                    "evidence_score": score["evidence_score"],
                    "reasoning": "规则层提示：{}".format("；".join(score["evidence"])),
                    "category": score["role"],
                    "related_symptoms": ["血压升高"],
                    "evidence_source": "结构化规则评分",
                })

    diagnosis_data["first_round_questions"] = merge_guardrail_questions(
        state,
        diagnosis_data.get("first_round_questions", [])
    )
    diagnosis_data["question_plan"] = {
        "phase": "安全分流与核心事实补齐",
        "missing_facts": state.get("missing_facts", []),
        "required_facts_complete": state.get("required_facts_complete", False),
    }
    return diagnosis_data


def apply_follow_up_guardrails(result: Dict[str, Any], session: DiagnosisSession) -> Dict[str, Any]:
    state = build_clinical_state(session.patient_info, session.symptoms, session.all_answers)
    session.clinical_state = state
    result["assessment_state"] = state
    result["red_flag_screening"] = state["red_flags"]

    if state["red_flags"]["is_emergency"]:
        result.update({
            "is_diagnosis_clear": True,
            "risk_stratification": "急诊/立即转诊",
            "next_round_questions": [],
            "reasoning_chain": "追问中出现红旗征，停止普通问诊并建议立即急诊。",
        })
        return result

    rule_scores = rule_based_diagnosis_scores(state, session.patient_info, session.symptoms)
    if rule_scores:
        result["rule_based_scores"] = rule_scores
        updates = result.setdefault("diagnosis_updates", [])
        existing_updates = {item.get("disease"): item for item in updates if isinstance(item, dict)}
        for score in rule_scores:
            if score["disease"] in existing_updates:
                existing_updates[score["disease"]]["evidence_score"] = score["evidence_score"]
                existing_updates[score["disease"]].setdefault("supporting_evidence", []).extend(score["evidence"])
            else:
                updates.append({
                    "disease": score["disease"],
                    "confidence": score["evidence_score"],
                    "evidence_score": score["evidence_score"],
                    "confidence_change": "规则层根据已收集核心事实更新评分",
                    "supporting_evidence": score["evidence"],
                    "ruling_out_evidence": [],
                    "evidence_source": "结构化规则评分",
                })

    result["next_round_questions"] = merge_guardrail_questions(
        state,
        result.get("next_round_questions", [])
    )
    result["question_plan"] = {
        "phase": "鉴别诊断追问" if state.get("required_facts_complete") else "核心事实补齐",
        "missing_facts": state.get("missing_facts", []),
        "required_facts_complete": state.get("required_facts_complete", False),
    }

    if not state.get("required_facts_complete", True):
        result["is_diagnosis_clear"] = False
    return result


def normalize_final_report(report: Dict[str, Any], session: DiagnosisSession) -> Dict[str, Any]:
    state = build_clinical_state(session.patient_info, session.symptoms, session.all_answers)
    rule_scores = rule_based_diagnosis_scores(state, session.patient_info, session.symptoms)
    diagnoses = report.get("diagnoses", []) if isinstance(report.get("diagnoses", []), list) else []

    likely = []
    differential = []
    must_not_miss = []
    comorbidities = []
    for item in diagnoses:
        disease = str(item.get("disease", ""))
        diagnosis_type = str(item.get("diagnosis_type", ""))
        lowered = disease + diagnosis_type
        if any(word in lowered for word in ["急诊", "心梗", "卒中", "主动脉夹层", "肺栓塞"]):
            must_not_miss.append(item)
        elif any(word in lowered for word in ["需排除", "待排除", "鉴别", "继发性"]):
            differential.append(item)
        elif any(word in lowered for word in ["共病", "OSA", "睡眠呼吸暂停"]):
            comorbidities.append(item)
        else:
            likely.append(item)

    report["assessment_state"] = state
    report["rule_based_scores"] = rule_scores
    report["primary_assessment"] = likely[0] if likely else (diagnoses[0] if diagnoses else None)
    report["likely_diagnoses"] = likely
    report["comorbidities_or_contributors"] = comorbidities
    report["differential_diagnoses"] = differential
    report["must_not_miss"] = must_not_miss
    report["care_level"] = "急诊/立即转诊" if state["red_flags"]["is_emergency"] else report.get("risk_stratification", "门诊进一步评估")
    report["diagnostic_boundaries"] = {
        "can_assess": "基于{}相关症状、问诊答案和已提供客观数据给出辅助判断".format(state.get("profile_label", "全科未分化疾病")),
        "cannot_confirm_without": state.get("missing_facts", []) + ["线下面诊体格检查", "必要实验室/影像/功能检查", "随访观察病程变化"],
        "must_not_miss": state.get("must_not_miss", []),
        "confidence_note": "百分比为辅助评分/模型估计，不等同于真实发病概率或确诊结论。",
    }
    return report


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
    red_flags = screen_red_flags(symptoms)
    if red_flags["is_emergency"]:
        first = red_flags["matched_red_flags"][0]
        return True, first["keyword"], first["category"]

    for symptom in symptoms:
        desc = symptom.description.lower()
        for emergency_key, emergency_desc in EMERGENCY_SYMPTOMS.items():
            if emergency_key in desc and not _contains_negative_context(desc, emergency_key):
                return True, emergency_key, emergency_desc
    return False, None, None

# ==================== DeepSeek API调用 ====================
# 创建全局HTTP客户端以复用连接，提升性能
_http_client = None

def get_http_client():
    """获取或创建全局HTTP客户端（连接池复用）"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=DEEPSEEK_TIMEOUT_SECONDS,
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            headers={"Content-Type": "application/json"}
        )
    return _http_client

@app.on_event("shutdown")
async def close_http_client():
    """应用关闭时释放HTTP连接池。"""
    global _http_client
    if _http_client is not None and not _http_client.is_closed:
        await _http_client.aclose()
    _http_client = None

async def call_deepseek(prompt: str, system_prompt: str = None, max_tokens: int = 2000) -> str:
    """调用DeepSeek API - 优化版（连接复用）"""
    if not has_valid_deepseek_key():
        raise HTTPException(status_code=503, detail="未配置有效的DEEPSEEK_API_KEY")

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
    
    last_error = None
    for attempt in range(DEEPSEEK_MAX_RETRIES + 1):
        client = get_http_client()
        started_at = time.perf_counter()
        try:
            response = await client.post(
                DEEPSEEK_BASE_URL + "/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            print("deepseek_ms={} attempt={} model={} max_tokens={}".format(
                elapsed_ms,
                attempt + 1,
                DEEPSEEK_MODEL,
                max_tokens,
            ))
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            print("DeepSeek API调用失败: {}".format(e))
            if status_code in {401, 403, 404} or attempt >= DEEPSEEK_MAX_RETRIES:
                raise HTTPException(status_code=502, detail="AI诊断服务调用失败: {}".format(str(e)))
            last_error = e
        except (httpx.TimeoutException, httpx.TransportError) as e:
            print("DeepSeek API网络异常，第{}次尝试失败: {}".format(attempt + 1, e))
            last_error = e
            global _http_client
            if _http_client is not None and not _http_client.is_closed:
                await _http_client.aclose()
            _http_client = None
            if attempt >= DEEPSEEK_MAX_RETRIES:
                raise HTTPException(status_code=502, detail="AI诊断服务网络异常: {}".format(str(e)))

        await asyncio.sleep(0.5 * (attempt + 1))

    raise HTTPException(status_code=502, detail="AI诊断服务调用失败: {}".format(str(last_error)))

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

CONCISE_OUTPUT_PROMPT = """

【输出风格】
1. 结论优先，只保留对诊断、分诊、下一步检查有影响的信息。
2. 不展开长篇思维链；reasoning_chain/clinical_reasoning 只写1-2句临床摘要。
3. 每个诊断的 reasoning 不超过80字，先写支持点，再写需要排除点。
4. evidence、suggestions、required_examinations、optional_examinations 每类最多3条。
5. 追问问题只问最关键的3个；每个问题一句话，选项短、互斥、可直接点击。
6. 不重复患者已提供的信息，不写泛泛科普，不输出处方剂量。
"""

# ==================== LLM临床思维链核心功能 ====================

async def generate_initial_diagnosis(request: DiagnosisRequest) -> Dict:
    """使用LLM生成初始诊断假设和第一轮问题"""
    clinical_state = build_clinical_state(request.patient, request.symptoms)
    
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
            "assessment_state": clinical_state,
            "red_flag_screening": clinical_state["red_flags"],
            "question_plan": {"phase": "急症分流", "missing_facts": [], "required_facts_complete": False},
            "disclaimer": "本系统仅提供辅助诊断参考，不替代面诊，需立即就医"
        }
    
    # 构建患者信息
    if FAST_INITIAL_RESPONSE:
        return build_fast_initial_diagnosis(clinical_state, request.patient, request.symptoms)

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
            "assessment_state": clinical_state,
            "red_flag_screening": clinical_state["red_flags"],
            "question_plan": {"phase": "急症分流", "missing_facts": [], "required_facts_complete": False},
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
        result = await call_deepseek(
            prompt,
            system_prompt=EVIDENCE_BASED_SYSTEM_PROMPT + CONCISE_OUTPUT_PROMPT,
            max_tokens=1800,
        )
        
        diagnosis_data = compact_llm_output(parse_llm_json_object(result))
        # 确保is_emergency字段存在
        if 'is_emergency' not in diagnosis_data:
            diagnosis_data['is_emergency'] = False
        return apply_initial_guardrails(diagnosis_data, clinical_state, request.patient, request.symptoms)
    except HTTPException:
        raise
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
            "assessment_state": clinical_state,
            "red_flag_screening": clinical_state["red_flags"],
            "question_plan": {
                "phase": "规则降级",
                "missing_facts": clinical_state.get("missing_facts", []),
                "required_facts_complete": clinical_state.get("required_facts_complete", False),
            },
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
    follow_up_system_prompt = EVIDENCE_BASED_SYSTEM_PROMPT + CONCISE_OUTPUT_PROMPT + """

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
        result = await call_deepseek(prompt, system_prompt=follow_up_system_prompt, max_tokens=1800)
        
        if LLM_DEBUG:
            print(f"[DEBUG] LLM原始返回长度: {len(result)}")
            print(f"[DEBUG] LLM原始返回前500字符: {result[:500]}")
        
        try:
            return apply_follow_up_guardrails(compact_llm_output(parse_llm_json_object(result)), session)
        except ValueError as parse_error:
            print(f"[ERROR] JSON解析失败: {parse_error}")
            return apply_follow_up_guardrails({
                "diagnosis_updates": [],
                "is_diagnosis_clear": False,
                "risk_stratification": "待评估",
                "next_round_questions": _generate_fallback_questions(session, current_round),
                "required_examinations": [],
                "optional_examinations": [],
                "reasoning_chain": "需要继续收集信息",
                "error_detail": "JSON解析失败，已启用备用问题集"
            }, session)
    except HTTPException:
        raise
    except Exception as e:
        print("生成追问问题失败: {}".format(e))
        import traceback
        traceback.print_exc()
        return apply_follow_up_guardrails({
            "diagnosis_updates": [],
            "is_diagnosis_clear": False,
            "risk_stratification": "待评估",
            "next_round_questions": _generate_fallback_questions(session, current_round),
            "required_examinations": [],
            "optional_examinations": [],
            "reasoning_chain": "需要继续收集信息",
            "error_detail": str(e)
        }, session)

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
    final_system_prompt = EVIDENCE_BASED_SYSTEM_PROMPT + CONCISE_OUTPUT_PROMPT + """

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
        result = await call_deepseek(prompt, system_prompt=final_system_prompt, max_tokens=2200)
        
        return compact_llm_output(normalize_final_report(compact_llm_output(parse_llm_json_object(result)), session))
    except HTTPException:
        raise
    except Exception as e:
        print("生成最终诊断失败: {}".format(e))
        import traceback
        traceback.print_exc()
        return normalize_final_report({
            "diagnoses": [],
            "required_examinations": [],
            "optional_examinations": [],
            "risk_stratification": "待评估",
            "clinical_reasoning": "诊断过程完成",
            "disclaimer": "本诊断仅供参考，请咨询执业医师"
        }, session)

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
    started_at = time.perf_counter()
    cleanup_expired_sessions()
    
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
        session.clinical_state = diagnosis_data.get('assessment_state', {})
        
        # 合并返回数据
        response_data = {
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
            "assessment_state": session.clinical_state,
            "red_flag_screening": diagnosis_data.get('red_flag_screening', {}),
            "question_plan": diagnosis_data.get('question_plan', {}),
            "rule_based_scores": diagnosis_data.get('rule_based_scores', []),
            "is_diagnosis_clear": False,
            "disclaimer": diagnosis_data.get('disclaimer', '本诊断仅供参考，请咨询执业医师')
        }
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        print("diagnosis_start_ms={} fast_initial={} symptom_count={}".format(
            elapsed_ms,
            bool(diagnosis_data.get("llm_deferred")),
            len(request.symptoms),
        ))
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/diagnosis/follow-up")
async def follow_up_diagnosis(request: FollowUpRequest):
    """继续追问流程"""
    cleanup_expired_sessions()
    
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
        if LLM_DEBUG:
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
        
        assessment_state = result.get('assessment_state', {}) if isinstance(result, dict) else {}
        if assessment_state and not assessment_state.get('required_facts_complete', True):
            is_clear = False

        # 如果诊断未明确但已达到最大轮次，也结束（智能收敛：4轮）
        if session.round_count >= 4 and not is_clear and assessment_state.get('required_facts_complete', True):
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
            question_plan = result.get('question_plan', {}) if isinstance(result, dict) else {}
            red_flag_screening = result.get('red_flag_screening', {}) if isinstance(result, dict) else {}
            rule_based_scores = result.get('rule_based_scores', []) if isinstance(result, dict) else []
        except Exception as build_err:
            print(f"[WARNING] 构建返回数据失败: {build_err}")
            diagnosis_updates = []
            risk_strat = '待评估'
            diagnosis_summary = ''
            reasoning_chain = '需要继续收集信息'
            required_exams = []
            optional_exams = []
            question_plan = {}
            red_flag_screening = {}
            rule_based_scores = []
        
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
            "assessment_state": assessment_state,
            "red_flag_screening": red_flag_screening,
            "question_plan": question_plan,
            "rule_based_scores": rule_based_scores,
            "round_count": session.round_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] 追问接口异常: {str(e)}")
        print(f"[ERROR] 详细堆栈: {error_trace}")
        raise HTTPException(status_code=500, detail="追问处理失败: {}".format(str(e)))

@app.post("/api/diagnosis/final")
async def final_diagnosis(request: FollowUpRequest):
    """获取最终诊断报告"""
    cleanup_expired_sessions()
    
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
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== 启动入口 ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
