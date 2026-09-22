import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "medrag_backend"))

from app.models import DiagnosisRequest, PatientInfo, Symptom, FollowUpAnswer
from app.services.diagnosis_service import DiagnosisService, WorkflowError
from app.services.llm_service import Assessment, ClinicalModelError, FinalReport, LLMService


class DiagnosisServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = DiagnosisService()
        self.stop_at = 6
        self.cases = []
        self.service.llm.assess = AsyncMock(side_effect=self.assess)
        self.service.llm.report = AsyncMock(return_value=FinalReport(
            clinical_reasoning="现有资料不足以确定病因。", diagnoses=[],
            missing_information=["查体结果"], care_plan=["建议面诊补充查体。"],
        ))
        self.request = DiagnosisRequest(
            patient=PatientInfo(age=42, gender="female", history="既往用药记录", allergies="药物过敏"),
            symptoms=[Symptom(description="咳嗽", duration_days=3), Symptom(description="口干")],
        )

    async def assess(self, case):
        self.cases.append(case)
        n = case["completed_rounds"]
        return Assessment(
            summary="根据已提供的信息继续核实。", is_emergency=False, emergency_warning="",
            information_sufficient=n >= self.stop_at,
            missing_information=[] if n >= self.stop_at else ["待补充"],
            questions=[dict(question=f"第{n + 1}阶段尚需核实的信息？", input_type="text", purpose="补充病史")],
        )

    def answers(self, response):
        return [FollowUpAnswer(question_id=q["question_id"], question="伪造的问题文字",
                               answer="未检查", answer_type="text") for q in response["next_round_questions"]]

    async def test_four_five_and_six_rounds_then_report_with_all_case_data(self):
        for stop_at in (4, 5, 6):
            self.stop_at = stop_at
            response = await self.service.start(self.request)
            sid = response["session_id"]
            for n in range(1, stop_at + 1):
                response = await self.service.follow_up(sid, self.answers(response))
                self.assertEqual(response["completed_rounds"], n)
                self.assertEqual(response["is_diagnosis_clear"], n == stop_at)
                if n < stop_at:
                    self.assertEqual(response["round_count"], n + 1)
                    self.assertTrue(response["next_round_questions"])
            report = await self.service.finalize(sid, [])
            self.assertEqual(report["completed_rounds"], stop_at)
            case = self.service.llm.report.call_args.args[0]
            self.assertEqual(len(case["answers"]), stop_at)
            self.assertEqual(len(case["symptoms"]), 2)
            self.assertEqual(case["patient"]["allergies"], "药物过敏")
            self.assertNotIn("伪造", case["answers"][0]["question"])
            self.assertNotIn("candidates", case)
            self.assertNotIn("references", case)
            self.assertNotIn("support_score", str(report))

    async def test_final_report_preserves_guidelines_and_reuses_cached_report(self):
        self.stop_at = 4
        response = await self.service.start(self.request)
        for _ in range(4):
            response = await self.service.follow_up(response['session_id'], self.answers(response))
        self.service.llm.report.return_value = FinalReport(
            clinical_reasoning="待核实", missing_information=["查体"], care_plan=["面诊评估"],
            diagnoses=[dict(disease="咳嗽待查", guideline_query="acute cough", basis=[
                dict(source_id="symptom:0", quote="咳嗽")], uncertainties=[], next_steps=[])])

        async def annotate(report, case, llm):
            report['diagnoses'][0]['references'] = [{'source_id': 'verified-test-source'}]
            report['diagnoses'][0]['guideline_status'] = 'matched'

        self.service.guidelines.annotate = AsyncMock(side_effect=annotate)
        result = await self.service.finalize(response['session_id'], [])
        self.assertEqual(result['diagnoses'][0]['references'][0]['source_id'], 'verified-test-source')
        self.assertEqual(await self.service.finalize(response['session_id'], []), result)
        self.service.guidelines.annotate.assert_awaited_once()

    async def test_model_cannot_end_before_four_rounds(self):
        self.stop_at = 0
        response = await self.service.start(self.request)
        for _ in range(3):
            self.assertFalse(response["is_diagnosis_clear"])
            response = await self.service.follow_up(response["session_id"], self.answers(response))
        self.assertFalse(response["is_diagnosis_clear"])

    async def test_no_graph_or_reference_files_needed(self):
        with patch.object(Path, "read_text", side_effect=AssertionError("No local corpus allowed")):
            service = DiagnosisService()
            service.llm = self.service.llm
            result = await service.start(self.request)
        self.assertEqual(result["differential_diagnoses"], [])

    async def test_empty_missing_and_stale_answers_do_not_advance(self):
        result = await self.service.start(self.request)
        sid = result["session_id"]
        with self.assertRaises(WorkflowError):
            await self.service.follow_up(sid, [])
        with self.assertRaises(WorkflowError):
            await self.service.finalize(sid, [])
        invalid = self.answers(result)
        invalid[0].question_id = "unknown"
        with self.assertRaises(WorkflowError):
            await self.service.follow_up(sid, invalid)
        self.assertEqual(self.service.sessions.get(sid).completed_rounds, 0)

    async def test_failure_rollback_retry_and_duplicate_submission(self):
        result = await self.service.start(self.request)
        sid = result["session_id"]
        answers = self.answers(result)
        self.service.llm.assess.side_effect = ClinicalModelError("Unavailable")
        with self.assertRaises(ClinicalModelError):
            await self.service.follow_up(sid, answers)
        self.assertEqual(self.service.sessions.get(sid).all_answers, [])
        self.service.llm.assess.side_effect = self.assess
        response = await self.service.follow_up(sid, answers)
        calls = self.service.llm.assess.call_count
        self.assertEqual(await self.service.follow_up(sid, answers), response)
        self.assertEqual(self.service.llm.assess.call_count, calls)
        self.assertEqual(self.service.sessions.get(sid).completed_rounds, 1)

    async def test_empty_model_questions_is_error_not_final_report(self):
        self.service.llm.assess.return_value = None
        self.service.llm.assess.side_effect = None
        self.service.llm.assess.return_value = Assessment(summary="待核实", is_emergency=False,
            emergency_warning="", information_sufficient=True, missing_information=[], questions=[])
        with self.assertRaises(ClinicalModelError):
            await self.service.start(self.request)

    async def test_emergency_after_answer_stops_without_disease_fallback(self):
        result = await self.service.start(self.request)
        self.service.llm.assess.side_effect = None
        self.service.llm.assess.return_value = Assessment(summary="报告了急症表现", is_emergency=True,
            emergency_warning="请立即就医。", information_sufficient=False, missing_information=[], questions=[])
        response = await self.service.follow_up(result["session_id"], self.answers(result))
        self.assertTrue(response["is_emergency"])
        report = await self.service.finalize(result["session_id"], [])
        self.assertEqual(report["diagnoses"], [])
        self.assertEqual(report["care_plan"], ["请立即就医。"])
        self.service.llm.report.assert_not_called()

    async def test_disabled_model_fails_without_local_fallback(self):
        llm = LLMService()
        llm.enabled = False
        with self.assertRaises(ClinicalModelError):
            await llm.assess({})

    async def test_http_routes_use_new_async_workflow_and_reject_premature_report(self):
        from app import main
        with patch.object(main, "service", self.service), TestClient(main.app) as client:
            response = client.post('/api/diagnosis/start', json=self.request.model_dump())
            self.assertEqual(response.status_code, 200)
            sid = response.json()['session_id']
            self.assertEqual(client.post('/api/diagnosis/final', json={"session_id": sid}).status_code, 409)
            self.service.llm.assess.side_effect = ClinicalModelError('Unavailable')
            self.assertEqual(client.post('/api/diagnosis/start', json=self.request.model_dump()).status_code, 503)
            self.assertFalse(client.get('/api/health').json()['local_graph_enabled'])

    async def test_invented_or_unknown_evidence_is_not_shown_in_report(self):
        self.stop_at = 4
        response = await self.service.start(self.request)
        for _ in range(4):
            response = await self.service.follow_up(response['session_id'], self.answers(response))
        self.service.llm.report.return_value = FinalReport(
            clinical_reasoning="待核实", missing_information=["检查结果"], care_plan=["面诊评估"],
            diagnoses=[dict(disease="未获证实的方向", basis=[
                dict(source_id="symptom:0", quote="患者有高血压"),
                dict(source_id="answer:r1_0:0", quote="未检查")], uncertainties=[], next_steps=[])])
        result = await self.service.finalize(response['session_id'], [])
        self.assertEqual(result['diagnoses'], [])


if __name__ == "__main__":
    unittest.main()
