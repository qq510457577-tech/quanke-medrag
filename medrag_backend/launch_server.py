#!/usr/bin/env python
"""
简单的服务器启动器
"""
import subprocess
import sys
import os

# 切换到后端目录
backend_dir = r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend"
os.chdir(backend_dir)

print(f"Working directory: {os.getcwd()}")
print("Starting server...")

# 启动服务器进程
process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "llm_diagnosis:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

# 实时打印输出
try:
    for line in process.stdout:
        print(line, end='')
except KeyboardInterrupt:
    print("\nStopping server...")
    process.terminate()
    process.wait()

print("Server process ended.")
