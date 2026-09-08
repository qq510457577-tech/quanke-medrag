import sys
import unittest


sys.path.insert(0, "medrag_backend")

from llm_diagnosis import (
    Symptom,
    format_answer_history,
    format_symptoms_for_prompt,
    screen_red_flags,
)


class ClinicalSafetyTests(unittest.TestCase):
    def test_negative_answer_does_not_trigger_question_keyword(self):
        result = screen_red_flags(
            [Symptom(description="头晕")],
            [{"question": "是否胸痛？", "answer": "否"}],
        )
        self.assertFalse(result["is_emergency"])

    def test_affirmative_answer_triggers_question_keyword(self):
        result = screen_red_flags(
            [Symptom(description="头晕")],
            [{"question": "是否胸痛？", "answer": "是"}],
        )
        self.assertTrue(result["is_emergency"])

    def test_multiple_symptoms_are_retained_in_prompt_context(self):
        context = format_symptoms_for_prompt([
            Symptom(description="胸闷", duration_days=2, severity=3),
            Symptom(description="双下肢水肿", duration_months=1, severity=5),
        ])
        self.assertIn("胸闷", context)
        self.assertIn("双下肢水肿", context)
        self.assertIn("2天", context)
        self.assertIn("1个月", context)

    def test_answer_history_is_bounded_and_keeps_most_recent_evidence(self):
        history = format_answer_history([
            {"question": "早期问题", "answer": "早期回答"},
            {"question": "关键问题", "answer": "关键回答"},
        ], max_items=1)
        self.assertNotIn("早期问题", history)
        self.assertIn("关键问题", history)
        self.assertIn("关键回答", history)


if __name__ == "__main__":
    unittest.main()
