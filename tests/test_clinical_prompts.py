import sys
import unittest


sys.path.insert(0, "medrag_backend")

from clinical_prompts import (
    FINAL_REPORT_SYSTEM_PROMPT,
    FOLLOW_UP_SYSTEM_PROMPT,
    GENERAL_CLINICAL_SYSTEM_PROMPT,
    build_final_report_prompt,
    build_follow_up_prompt,
    build_initial_prompt,
)


class ClinicalPromptTests(unittest.TestCase):
    def setUp(self):
        self.patient = {"age": 56, "gender": "男", "history": "高血压", "allergies": "无"}
        self.symptoms = [{"description": "胸闷", "duration": "2天", "severity": "中"}]
        self.answers = [{"round": 1, "question": "是否胸痛", "answer": "否"}]
        self.hypotheses = [{"disease": "心律失常", "confidence": 45}]

    def test_system_prompt_sets_chinese_patient_output_boundary(self):
        self.assertIn("Simplified Chinese", GENERAL_CLINICAL_SYSTEM_PROMPT)
        self.assertIn("not a disease", GENERAL_CLINICAL_SYSTEM_PROMPT)

    def test_follow_up_prompt_has_complete_case_and_json_contract(self):
        prompt = build_follow_up_prompt(
            self.patient, self.symptoms, self.answers, self.hypotheses, current_round=2
        )
        self.assertIn("CASE_DATA", prompt)
        self.assertIn("胸闷", prompt)
        self.assertIn("next_round_questions", prompt)
        self.assertIn("maximum_rounds=6", prompt)
        self.assertIn("exactly three", FOLLOW_UP_SYSTEM_PROMPT)

    def test_initial_and_final_prompts_keep_required_contracts(self):
        initial = build_initial_prompt(self.patient, self.symptoms, {"focus": "general"})
        final = build_final_report_prompt(self.patient, self.symptoms, self.answers, self.hypotheses)
        self.assertIn("first_round_questions", initial)
        self.assertIn("required_examinations", final)
        self.assertIn("at most three", FINAL_REPORT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
