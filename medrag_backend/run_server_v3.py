#!/usr/bin/env python
import sys
import os

# 确保当前目录是后端目录
os.chdir(r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")
sys.path.insert(0, r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")

try:
    import uvicorn
    print("Starting server...")
    uvicorn.run("llm_diagnosis:app", host="0.0.0.0", port=8000, log_level="info")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

input("Press Enter to exit...")
