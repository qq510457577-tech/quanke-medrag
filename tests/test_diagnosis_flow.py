import unittest

from fastapi.testclient import TestClient

from medrag_backend.app.main import app


class DiagnosisFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_full_flow(self) -> None:
        start_payload = {
            "patient": {"age": 58, "gender": "男", "history": "高血压", "allergies": ""},
            "symptoms": [{"description": "胸痛伴胸闷2天，活动后加重", "duration_days": 2, "severity": 4}],
        }
        start_response = self.client.post("/api/diagnosis/start", json=start_payload)
        self.assertEqual(start_response.status_code, 200)
        start_data = start_response.json()
        self.assertIn("session_id", start_data)
        self.assertTrue(start_data["first_round_questions"])

        follow_payload = {
            "session_id": start_data["session_id"],
            "answers": [
                {
                    "question_id": start_data["first_round_questions"][0]["question_id"],
                    "question": start_data["first_round_questions"][0]["question"],
                    "answer": "压榨样",
                    "answer_type": "single",
                }
            ],
        }
        follow_response = self.client.post("/api/diagnosis/follow-up", json=follow_payload)
        self.assertEqual(follow_response.status_code, 200)
        follow_data = follow_response.json()
        self.assertIn("diagnosis_updates", follow_data)

        final_payload = {"session_id": start_data["session_id"], "answers": []}
        final_response = self.client.post("/api/diagnosis/final", json=final_payload)
        self.assertEqual(final_response.status_code, 200)
        final_data = final_response.json()
        self.assertTrue(final_data["diagnoses"])
        self.assertTrue(final_data["references"])


if __name__ == "__main__":
    unittest.main()
