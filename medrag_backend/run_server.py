import sys
import os

# Change to backend directory
os.chdir(r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")
sys.path.insert(0, r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")

print(f"Working directory: {os.getcwd()}")

# Try to import and run
try:
    import uvicorn
    from llm_diagnosis import app
    print("Import successful, starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
