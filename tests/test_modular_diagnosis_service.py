import asyncio
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1] / "medrag_backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.models import DiagnosisRequest, FollowUpAnswer, PatientInfo, Symptom  # noqa: E402
from app.services.diagnosis_service import DiagnosisService  # noqa: E402


class DiagnosisServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = DiagnosisService()
        self.service.llm.enabled = False

    def test_start_returns_bounded_question_round_and_support_ranking(self):
        result = self.service.start(
            DiagnosisRequest(
                patient=PatientInfo(age=45, gender="male"),
                symptoms=[Symptom(description="咳嗽", duration_days=5, severity=3)],
            )
        )

        self.assertEqual(result["round_count"], 1)
        self.assertEqual(result["max_rounds"], 6)
        self.assertLessEqual(len(result["first_round_questions"]), 3)
        self.assertTrue(result["differential_diagnoses"])
        self.assertIn("confidence", result["differential_diagnoses"][0])

    def test_early_stop_requires_four_completed_rounds_and_clear_evidence_margin(self):
        candidates = [{"confidence": 82}, {"confidence": 60}]
        self.assertFalse(self.service._is_diagnosis_clear(candidates, 3, 6))
        self.assertTrue(self.service._is_diagnosis_clear(candidates, 4, 6))
        self.assertFalse(self.service._is_diagnosis_clear([{"confidence": 82}, {"confidence": 70}], 4, 6))

    def test_cough_path_has_questions_through_four_clinical_stages(self):
        started = self.service.start(
            DiagnosisRequest(
                patient=PatientInfo(age=45, gender="male"),
                symptoms=[Symptom(description="咳嗽", duration_days=5, severity=3)],
            )
        )
        session_id = started["session_id"]
        questions = started["first_round_questions"]

        for completed_round in range(1, 4):
            question = questions[0]
            result = self.service.follow_up(
                session_id,
                [
                    FollowUpAnswer(
                        question_id=question["question_id"],
                        question=question["question"],
                        answer="没有",
                        answer_type=question["input_type"],
                    )
                ],
            )
            self.assertFalse(result["is_diagnosis_clear"])
            self.assertEqual(result["completed_rounds"], completed_round)
            self.assertTrue(result["next_round_questions"])
            questions = result["next_round_questions"]

    def test_final_report_uses_support_score_not_probability(self):
        started = self.service.start(
            DiagnosisRequest(
                patient=PatientInfo(age=30, gender="female"),
                symptoms=[Symptom(description="头痛", duration_days=2, severity=3)],
            )
        )
        question = started["first_round_questions"][0]
        report = asyncio.run(
            self.service.finalize(
                started["session_id"],
                [
                    FollowUpAnswer(
                        question_id=question["question_id"],
                        question=question["question"],
                        answer="否",
                        answer_type=question["input_type"],
                    )
                ],
            )
        )

        self.assertTrue(report["diagnoses"])
        self.assertIn("support_score", report["diagnoses"][0])
        self.assertNotIn("probability", report["diagnoses"][0])


if __name__ == "__main__":
    unittest.main()
