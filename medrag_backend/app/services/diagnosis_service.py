from __future__ import annotations

import uuid
from copy import deepcopy

from ..config import MAX_FOLLOW_UP_ROUNDS
from ..models import DiagnosisRequest, DiagnosisSession, FollowUpAnswer
from .llm_service import Assessment, ClinicalModelError, LLMService
from .session_store import SessionStore


ROUND_FOCUS = [
    "Characterize the presenting symptoms and screen early urgency.",
    "Clarify discriminating associated positive and negative symptoms.",
    "Clarify relevant medication, medical and exposure history.",
    "Obtain available vital signs and focused examination findings; record absent examinations as unknown.",
    "Obtain available investigation results and remaining discriminating facts.",
    "Clarify unresolved contradictions, symptom evolution and access to reassessment; do not repeat unknowns.",
]
UNKNOWN_ANSWERS = {"不清楚/未检查", "不清楚", "不知道", "未知", "未检查", "暂无", "未测量", "不确定"}


class WorkflowError(ValueError):
    pass


class DiagnosisService:
    def __init__(self) -> None:
        self.sessions = SessionStore()
        self.llm = LLMService()
        self._busy: set[str] = set()

    @staticmethod
    def _case(session: DiagnosisSession) -> dict:
        sources = [{"source_id": f"symptom:{i}", "text": s.description} for i, s in enumerate(session.symptoms)]
        for answer in session.all_answers:
            values = answer["answer"] if isinstance(answer["answer"], list) else [answer["answer"]]
            for i, value in enumerate(values):
                if isinstance(value, str) and value.strip() not in UNKNOWN_ANSWERS:
                    sources.append({"source_id": f"answer:{answer['question_id']}:{i}", "text": value})
        return {
            "patient": session.patient_info.model_dump(),
            "symptoms": [item.model_dump() for item in session.symptoms],
            "answers": session.all_answers,
            "completed_rounds": session.completed_rounds,
            "minimum_rounds": 4,
            "maximum_rounds": session.max_rounds,
            "next_focus": ROUND_FOCUS[min(session.completed_rounds, 5)],
            "evidence_sources": sources,
        }

    @staticmethod
    def _apply(session: DiagnosisSession, assessment: Assessment) -> None:
        if assessment.is_emergency and not assessment.emergency_warning.strip():
            raise ClinicalModelError("急症评估信息不完整，请重试；如有急危重症表现请立即就医。")
        ready = session.completed_rounds >= 4 and assessment.information_sufficient and not assessment.missing_information
        session.is_emergency = assessment.is_emergency
        session.emergency_warning = assessment.emergency_warning if assessment.is_emergency else None
        session.is_diagnosis_clear = bool(assessment.is_emergency or ready or session.completed_rounds >= session.max_rounds)
        session.summary = assessment.summary
        session.round_count = min(session.completed_rounds + 1, session.max_rounds)
        session.current_questions = []
        if session.is_diagnosis_clear:
            return
        if not assessment.questions:
            raise ClinicalModelError("追问信息不完整，本轮未推进，请重试。")
        previous = {item["question"].strip() for item in session.all_answers}
        for index, question in enumerate(assessment.questions):
            if question.question.strip() in previous:
                continue
            previous.add(question.question.strip())
            item = question.model_dump()
            if question.input_type != "text":
                if not item["options"]:
                    raise ClinicalModelError("追问选项不完整，本轮未推进，请重试。")
                if "不清楚/未检查" not in item["options"]:
                    item["options"].append("不清楚/未检查")
            item["question_id"] = f"r{session.round_count}_{index}"
            session.current_questions.append(item)
        if not session.current_questions:
            raise ClinicalModelError("追问与已有回答重复，本轮未推进，请重试。")

    @staticmethod
    def _response(session: DiagnosisSession) -> dict:
        return {
            "session_id": session.session_id,
            "round_count": session.round_count,
            "completed_rounds": session.completed_rounds,
            "max_rounds": session.max_rounds,
            "is_diagnosis_clear": session.is_diagnosis_clear,
            "is_emergency": session.is_emergency,
            "emergency_warning": session.emergency_warning,
            "reasoning_chain": session.summary,
            "differential_diagnoses": [],
            "diagnosis_updates": [],
            "first_round_questions": session.current_questions,
            "next_round_questions": session.current_questions,
        }

    async def start(self, request: DiagnosisRequest) -> dict:
        if not request.symptoms or not any(s.description.strip() for s in request.symptoms):
            raise WorkflowError("请至少填写一个症状。")
        session = DiagnosisSession(
            session_id=str(uuid.uuid4()), patient_info=request.patient,
            symptoms=[s for s in request.symptoms if s.description.strip()],
            max_rounds=MAX_FOLLOW_UP_ROUNDS,
        )
        self._apply(session, await self.llm.assess(self._case(session)))
        self.sessions.save(session)
        return self._response(session)

    def _get(self, session_id: str) -> DiagnosisSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise KeyError("会话已过期，请重新开始。")
        if session_id in self._busy:
            raise WorkflowError("本轮正在处理，请等待返回结果。")
        return session

    async def follow_up(self, session_id: str, answers: list[FollowUpAnswer]) -> dict:
        original = self._get(session_id)
        signature = [(a.question_id, a.answer) for a in answers]
        if signature == original.last_submission and original.last_response:
            return original.last_response
        if original.is_diagnosis_clear:
            raise WorkflowError("问诊已完成，请获取报告。")
        questions = {q["question_id"]: q for q in original.current_questions}
        if len(answers) != len(questions) or {a.question_id for a in answers} != set(questions):
            raise WorkflowError("请完成本轮全部问题；未知信息可选择不清楚或未检查。")
        session = deepcopy(original)
        for answer in answers:
            question = questions[answer.question_id]
            value = answer.answer
            if value is None or value == "" or value == []:
                raise WorkflowError("本轮存在未回答的问题。")
            options = question["options"]
            if question["input_type"] == "single" and value not in options:
                raise WorkflowError("答案不在本轮选项中。")
            if question["input_type"] == "multiple" and (not isinstance(value, list) or any(v not in options for v in value)):
                raise WorkflowError("请选择有效的多选答案。")
            if question["input_type"] == "text" and (not isinstance(value, str) or not value.strip()):
                raise WorkflowError("请填写有效的文字回答。")
            session.all_answers.append({
                "round": original.round_count, "question_id": answer.question_id,
                "question": question["question"], "answer": value,
                "answer_type": question["input_type"],
            })
        session.completed_rounds += 1
        self._busy.add(session_id)
        try:
            self._apply(session, await self.llm.assess(self._case(session)))
            response = self._response(session)
            session.last_submission = signature
            session.last_response = response
            self.sessions.save(session)
            return response
        finally:
            self._busy.discard(session_id)

    async def finalize(self, session_id: str, answers: list[FollowUpAnswer]) -> dict:
        session = self._get(session_id)
        if not session.is_diagnosis_clear:
            raise WorkflowError("尚未完成递进问诊，请继续回答本轮问题。")
        if answers:
            raise WorkflowError("请先通过追问接口提交回答，再生成报告。")
        if session.final_report is not None:
            return session.final_report
        self._busy.add(session_id)
        try:
            if session.is_emergency:
                report = {
                    "diagnoses": [], "clinical_reasoning": session.summary,
                    "care_plan": [session.emergency_warning],
                }
            else:
                case = self._case(session)
                report = (await self.llm.report(case)).model_dump()
                sources = {s["source_id"]: s["text"] for s in case["evidence_sources"]}
                grounded = []
                for diagnosis in report["diagnoses"]:
                    quotes = [e["quote"] for e in diagnosis["basis"]
                              if e["source_id"] in sources and e["quote"].strip()
                              and e["quote"] in sources[e["source_id"]]]
                    if quotes:
                        diagnosis["basis"] = list(dict.fromkeys(quotes))
                        grounded.append(diagnosis)
                report["diagnoses"] = grounded
            report.update({
                "session_id": session_id, "completed_rounds": session.completed_rounds,
                "is_emergency": session.is_emergency, "emergency_warning": session.emergency_warning,
                "references": [],
            })
            session.final_report = report
            self.sessions.save(session)
            return report
        finally:
            self._busy.discard(session_id)
