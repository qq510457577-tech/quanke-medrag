from __future__ import annotations

import uuid
from typing import Any, Dict, List

from ..config import MAX_FOLLOW_UP_ROUNDS, QUESTIONS_PER_ROUND
from ..models import DiagnosisRequest, DiagnosisSession, FollowUpAnswer
from .knowledge_service import ROUND_FOCUS, KnowledgeService
from .llm_service import LLMService
from .reference_service import ReferenceService
from .retrieval_service import LocalVectorRetriever
from .session_store import SessionStore


class DiagnosisService:
    def __init__(self) -> None:
        self.sessions = SessionStore()
        self.knowledge = KnowledgeService()
        self.references = ReferenceService()
        self.llm = LLMService()
        self.retriever = LocalVectorRetriever()

    def _attach_references(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for item in candidates:
            refs = self.references.get_many(item.get("reference_ids", []))
            normalized.append(
                {
                    "disease": item["disease"],
                    "confidence": item["confidence"],
                    "category": item["category"],
                    "reasoning": item["reasoning"],
                    "related_symptoms": item["related_symptoms"],
                    "evidence_source": item["evidence_source"],
                    "references": refs[:2],
                }
            )
        return normalized

    def _unique_references(self, references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique = []
        seen = set()
        for item in references:
            key = item.get("id") or f"{item.get('title')}::{item.get('source')}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _build_rag_query(self, session: DiagnosisSession, answers: List[FollowUpAnswer], candidates: List[Dict[str, Any]]) -> str:
        symptom_text = " ".join(item.description for item in session.symptoms)
        answer_text = " ".join(f"{item.question} {item.answer}" for item in answers)
        candidate_text = " ".join(item["disease"] for item in candidates[:3])
        return f"{symptom_text} {answer_text} {candidate_text} 基层全科 指南 诊断 依据"

    def start(self, request: DiagnosisRequest) -> Dict[str, Any]:
        is_emergency, emergency_type, emergency_warning = self.knowledge.detect_emergency(request.symptoms)
        raw_candidates = self.knowledge.infer_candidates(request.symptoms)
        candidates = self._attach_references(raw_candidates)
        questions = self.knowledge.build_questions(request.symptoms, 1, raw_candidates)[:QUESTIONS_PER_ROUND]

        session = DiagnosisSession(
            session_id=request.session_id or str(uuid.uuid4()),
            patient_info=request.patient,
            symptoms=request.symptoms,
            diagnosis_hypothesis=candidates,
            current_questions=questions,
            round_count=1,
            max_rounds=MAX_FOLLOW_UP_ROUNDS,
            is_emergency=is_emergency,
            emergency_type=emergency_type,
            emergency_warning=emergency_warning,
            stage_label=ROUND_FOCUS[1],
        )
        self.sessions.save(session)

        required = raw_candidates[0].get("recommended_exams", [])[:3] if raw_candidates else []
        return {
            "session_id": session.session_id,
            "symptom_analysis": self.knowledge.summarize_reasoning(request.symptoms, [], raw_candidates),
            "knowledge_graph_hits": self.knowledge.build_graph_context(request.symptoms, []),
            "is_emergency": is_emergency,
            "emergency_type": emergency_type,
            "emergency_warning": emergency_warning,
            "risk_stratification": "急诊/尽快就医" if is_emergency else "继续分层追问",
            "differential_diagnoses": candidates,
            "first_round_questions": questions,
            "required_examinations": [{"name": item, "reason": "用于缩小鉴别诊断范围"} for item in required],
            "optional_examinations": [],
            "reasoning_chain": "采用 MedRAG 风格的图谱引导检索：先定位未分化症状，再按红旗征、阳性症状、检查结果逐轮收敛。",
            "stage_label": ROUND_FOCUS[1],
            "disclaimer": "结果仅供基层全科辅助参考，不能替代线下面诊和正式诊断。",
        }

    def follow_up(self, session_id: str, answers: List[FollowUpAnswer]) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            raise KeyError("session not found")

        old_candidates = list(session.diagnosis_hypothesis)
        for answer in answers:
            session.all_answers.append(
                {
                    "round": session.round_count,
                    "question_id": answer.question_id,
                    "question": answer.question,
                    "answer": answer.answer,
                    "answer_type": answer.answer_type,
                }
            )

        next_round = min(session.round_count + 1, session.max_rounds)
        typed_answers = [FollowUpAnswer(**item) for item in session.all_answers]
        raw_candidates = self.knowledge.infer_candidates(session.symptoms, typed_answers)
        candidates = self._attach_references(raw_candidates)
        session.diagnosis_hypothesis = candidates
        session.round_count = next_round
        session.stage_label = ROUND_FOCUS[next_round]
        is_clear = next_round >= session.max_rounds
        next_questions = [] if is_clear else self.knowledge.build_questions(session.symptoms, next_round, raw_candidates)
        session.current_questions = next_questions
        self.sessions.save(session)

        previous_scores = {item["disease"]: item["confidence"] for item in old_candidates}
        updates = []
        for item in candidates[:3]:
            before = previous_scores.get(item["disease"], item["confidence"])
            updates.append(
                {
                    "disease": item["disease"],
                    "confidence": item["confidence"],
                    "confidence_change": f"较上一轮 {'上升' if item['confidence'] >= before else '下降'}到 {item['confidence']}%",
                    "supporting_evidence": item["related_symptoms"],
                }
            )

        return {
            "session_id": session.session_id,
            "diagnosis_updates": updates,
            "is_diagnosis_clear": is_clear,
            "risk_stratification": "建议尽快完善检查" if session.is_emergency else "继续追问",
            "diagnosis_summary": self.knowledge.summarize_reasoning(session.symptoms, typed_answers, raw_candidates),
            "knowledge_graph_hits": self.knowledge.build_graph_context(session.symptoms, typed_answers),
            "next_round_questions": next_questions[:QUESTIONS_PER_ROUND],
            "reasoning_chain": ROUND_FOCUS[next_round],
            "required_examinations": [],
            "optional_examinations": [],
            "stage_label": ROUND_FOCUS[next_round],
        }

    async def finalize(self, session_id: str, answers: List[FollowUpAnswer]) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            raise KeyError("session not found")

        for answer in answers:
            session.all_answers.append(
                {
                    "round": session.round_count,
                    "question_id": answer.question_id,
                    "question": answer.question,
                    "answer": answer.answer,
                    "answer_type": answer.answer_type,
                }
            )

        typed_answers = [FollowUpAnswer(**item) for item in session.all_answers]
        raw_candidates = self.knowledge.infer_candidates(session.symptoms, typed_answers)
        candidates = self._attach_references(raw_candidates)
        basis = self.knowledge.final_basis(raw_candidates, typed_answers)
        evidence_refs = []
        for item in candidates[:3]:
            evidence_refs.extend(item.get("references", []))
        rag_query = self._build_rag_query(session, typed_answers, raw_candidates)
        evidence_refs.extend(self.retriever.retrieve_as_references(rag_query, top_k=4))
        evidence_refs = self._unique_references(evidence_refs)

        patient_summary = self.knowledge.summarize_reasoning(session.symptoms, typed_answers, raw_candidates)
        refined = await self.llm.refine_final_report(
            patient_summary=patient_summary,
            candidates=raw_candidates,
            reasoning=patient_summary,
            references=evidence_refs,
        )

        if refined and refined.get("diagnoses"):
            diagnoses = []
            for idx, candidate in enumerate(raw_candidates[:3]):
                llm_item = refined["diagnoses"][idx] if idx < len(refined["diagnoses"]) else {}
                diagnoses.append(
                    {
                        "name": llm_item.get("name", candidate["disease"]),
                        "probability": llm_item.get("probability", candidate["confidence"]),
                        "basis": llm_item.get("basis", [candidate["reasoning"]]),
                        "next_steps": llm_item.get("next_steps", candidate.get("recommended_exams", [])),
                    }
                )
            clinical_reasoning = refined.get("clinical_reasoning", patient_summary)
        else:
            diagnoses = [
                {
                    "name": item["disease"],
                    "probability": item["confidence"],
                    "basis": [item["reasoning"]],
                    "next_steps": item.get("recommended_exams", []),
                }
                for item in raw_candidates[:3]
            ]
            clinical_reasoning = patient_summary

        return {
            "session_id": session.session_id,
            "diagnoses": diagnoses,
            "major_diagnosis": diagnoses[0]["name"] if diagnoses else "待明确",
            "minor_diagnoses": [item["name"] for item in diagnoses[1:3]],
            "knowledge_graph_hits": self.knowledge.build_graph_context(session.symptoms, typed_answers),
            "diagnostic_basis": basis,
            "references": evidence_refs[:4],
            "evidence_paragraphs": [p for ref in evidence_refs[:2] for p in ref.get("evidence_paragraphs", [])[:2]],
            "highlights": [h for ref in evidence_refs[:2] for p in ref.get("evidence_paragraphs", [])[:2] for h in p.get("highlights", [])[:3]],
            "clinical_reasoning": clinical_reasoning,
            "reasoning_chain": patient_summary,
            "care_plan": [
                "根据主要诊断完善首选检查并动态复评。",
                "若出现红旗征或症状快速进展，及时转诊或急诊处理。",
                "结合基层可获得资源进行随访管理与健康教育。",
            ],
        }
