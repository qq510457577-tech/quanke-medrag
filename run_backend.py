import subprocess
import sys
import os

# 切换到后端目录
os.chdir('medrag_backend')

# 启动uvicorn
subprocess.run([sys.executable, '-m', 'uvicorn', 'llm_diagnosis:app', '--host', '0.0.0.0', '--port', '8000'])
