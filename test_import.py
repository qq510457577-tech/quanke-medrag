import sys
sys.path.insert(0, r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")
try:
    import llm_diagnosis
    print("Import OK")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
