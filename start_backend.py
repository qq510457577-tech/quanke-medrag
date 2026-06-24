import sys
sys.path.insert(0, r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend")

import uvicorn
from llm_diagnosis import app

print("Starting server on port 8000...")
uvicorn.run(app, host="0.0.0.0", port=8000)
