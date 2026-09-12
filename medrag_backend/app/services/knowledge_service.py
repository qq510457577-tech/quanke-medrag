from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from ..config import GRAPH_DIR
from ..models import FollowUpAnswer, Symptom


ROUND_FOCUS = {
    1: "症状特征刻画",
    2: "阳性与阴性症状追问",
    3: "危险分层与红旗征排查",
    4: "体征与床旁检查补充",
    5: "检查检验结果整合",
    6: "诊断收敛与处置建议",
}

EMERGENCY_HINTS = {
    "胸痛": "胸痛需警惕急性冠脉综合征、主动脉夹层、肺栓塞等急症。",
    "胸闷": "胸闷伴呼吸困难或活动后明显加重时需优先排查心肺高危疾病。",
    "头痛": "突发最严重头痛、意识改变或局灶神经功能缺损需要急诊评估。",
    "发热": "持续高热伴精神差、低血压或呼吸困难时需要尽快面诊。",
    "腹痛": "急性腹痛伴反跳痛、持续呕吐或黑便便血需尽快线下评估。",
}


def _normalize_text(value: str) -> str:
    return (value or "").strip().lower()


class KnowledgeService:
    def __init__(self) -> None:
        graph_path = Path(GRAPH_DIR) / "undifferentiated_symptom_graph.json"
        payload = json.loads(graph_path.read_text(encoding="utf-8"))
        self.graph = payload["symptoms"]

    def _find_symptom_nodes(
        self,
        symptoms: List[Symptom],
        answers: List[FollowUpAnswer] | None = None,
    ) -> List[Dict]:
        symptom_text = " ".join(item.description for item in symptoms)
        answer_text = " ".join(str(item.answer) for item in answers or [])
        merged = _normalize_text(f"{symptom_text} {answer_text}")
        matched = []
        for node in self.graph:
            aliases = [_normalize_text(node["name"])] + [_normalize_text(item) for item in node.get("aliases", [])]
            if any(alias and alias in merged for alias in aliases):
                matched.append(node)
        if not matched and self.graph:
            matched.append(self.graph[0])
        return matched

    def detect_emergency(self, symptoms: List[Symptom]) -> Tuple[bool, str | None, str | None]:
        merged = " ".join(item.description for item in symptoms)
        for keyword, warning in EMERGENCY_HINTS.items():
            if keyword in merged:
                return True, keyword, warning
        return False, None, None

    def infer_candidates(self, symptoms: List[Symptom], answers: List[FollowUpAnswer] | None = None) -> List[Dict]:
        matched_nodes = self._find_symptom_nodes(symptoms, answers)
        disease_scores: Dict[str, int] = defaultdict(int)
        disease_payloads: Dict[str, Dict] = {}

        for node in matched_nodes:
            for disease in node.get("common_diseases", []):
                score = int(disease.get("base_score", 20))
                disease_scores[disease["name"]] += score
                disease_payloads[disease["name"]] = disease

        candidates = []
        for disease_name, score in sorted(disease_scores.items(), key=lambda item: item[1], reverse=True)[:5]:
            payload = disease_payloads[disease_name]
            candidates.append(
                {
                    "disease": disease_name,
                    "confidence": min(92, score),
                    "category": payload.get("category", "未分类"),
                    "reasoning": "；".join(payload.get("clues", [])[:3]),
                    "related_symptoms": payload.get("related_symptoms", []),
                    "evidence_source": "本地 MedRAG 知识图谱检索",
                    "reference_ids": payload.get("reference_ids", []),
                    "recommended_exams": payload.get("recommended_exams", []),
                }
            )
        return candidates

    def build_questions(self, symptoms: List[Symptom], round_index: int, candidates: List[Dict]) -> List[Dict]:
        matched_nodes = self._find_symptom_nodes(symptoms)
        questions: List[Dict] = []
        seen = set()
        for node in matched_nodes:
            for item in node.get("question_bank", []):
                if item.get("round") != round_index:
                    continue
                key = item["question"]
                if key in seen:
                    continue
                seen.add(key)
                target_disease = candidates[0]["disease"] if candidates else "待明确"
                questions.append(
                    {
                        "question_id": item["question_id"],
                        "question": item["question"],
                        "input_type": item["input_type"],
                        "options": item["options"],
                        "target_symptom": node["name"],
                        "target_disease": target_disease,
                        "purpose": item["purpose"],
                        "clinical_intent": ROUND_FOCUS[round_index],
                    }
                )
                if len(questions) == 3:
                    return questions
        return questions

    def summarize_reasoning(self, symptoms: List[Symptom], answers: List[FollowUpAnswer], candidates: List[Dict]) -> str:
        symptom_summary = "、".join(item.description for item in symptoms[:3])
        answer_summary = "；".join(f"{item.question}:{item.answer}" for item in answers[-3:])
        lead = candidates[0]["disease"] if candidates else "待明确"
        fragments = [f"围绕主诉 {symptom_summary} 进行未分化症状初筛"]
        if answer_summary:
            fragments.append(f"结合近期追问结果 {answer_summary}")
        fragments.append(f"当前诊断权重最高的是 {lead}")
        return "，".join(fragments) + "。"

    def build_graph_context(self, symptoms: List[Symptom], answers: List[FollowUpAnswer] | None = None) -> List[Dict]:
        nodes = self._find_symptom_nodes(symptoms, answers)
        context = []
        for node in nodes[:3]:
            context.append(
                {
                    "symptom": node["name"],
                    "body_parts": node.get("body_parts", []),
                    "activity_limitations": node.get("activity_limitations", []),
                    "candidate_diseases": [item["name"] for item in node.get("common_diseases", [])[:3]],
                }
            )
        return context

    def final_basis(self, candidates: List[Dict], answers: List[FollowUpAnswer]) -> List[Dict]:
        answer_lines = [f"{item.question} -> {item.answer}" for item in answers]
        basis = []
        for candidate in candidates[:3]:
            basis.append(
                {
                    "diagnosis": candidate["disease"],
                    "basis": candidate["reasoning"],
                    "supporting_answers": answer_lines[:4],
                    "recommended_exams": candidate.get("recommended_exams", []),
                }
            )
        return basis
