import sys
sys.path.insert(0, r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")

from llm_diagnosis import check_emergency, Symptom

# Test emergency detection
test_symptoms = [
    Symptom(description="突发胸痛2小时", duration_years=0, duration_months=0, duration_days=0, severity=5)
]

is_emergency, emergency_type, emergency_desc = check_emergency(test_symptoms)
print(f"Is Emergency: {is_emergency}")
print(f"Emergency Type: {emergency_type}")
print(f"Emergency Desc: {emergency_desc}")
