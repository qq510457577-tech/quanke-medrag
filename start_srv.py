import sys
sys.path.insert(0, r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")

import uvicorn

print("Starting server on port 8000...")

# 直接运行
from llm_diagnosis import app
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
