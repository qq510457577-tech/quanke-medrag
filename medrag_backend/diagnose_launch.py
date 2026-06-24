#!/usr/bin/env python
"""
诊断启动器 - 捕获所有输出和错误
"""
import subprocess
import sys
import os

# 切换到后端目录
backend_dir = r"C:\Users\Administrator\.minimax-agent-cn\projects\1\medrag_backend"
os.chdir(backend_dir)

print(f"Working directory: {os.getcwd()}")
print(f"Python executable: {sys.executable}")
print("Checking Python environment...")

# 检查uvicorn是否可用
result = subprocess.run(
    [sys.executable, "-m", "uvicorn", "--help"],
    capture_output=True,
    text=True
)
print(f"uvicorn help output:\n{result.stdout}")
if result.stderr:
    print(f"uvicorn errors:\n{result.stderr}")

print("\n" + "="*50)
print("Starting server...")

# 启动服务器进程
process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "llm_diagnosis:app", "--host", "0.0.0.0", "--port", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# 等待几秒钟看是否有输出
import time
time.sleep(3)

# 检查进程状态
if process.poll() is not None:
    stdout, stderr = process.communicate()
    print(f"Server process exited with code: {process.returncode}")
    print(f"STDOUT:\n{stdout}")
    print(f"STDERR:\n{stderr}")
else:
    print("Server is running!")
    # 读取一些输出
    import select
    import fcntl
    
    # 设置为非阻塞
    import sys
    if sys.platform != 'win32':
        fd = process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
    
    # 读取输出
    time.sleep(2)
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            print(line, end='')
    except:
        pass
    
    print("\nServer started successfully!")
    print(f"Process ID: {process.pid}")
