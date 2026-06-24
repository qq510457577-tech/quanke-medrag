import subprocess
import sys

# 使用uvicorn启动服务
subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "medrag_backend.llm_diagnosis:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
)
print("Backend service started on port 8000")
