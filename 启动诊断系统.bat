@echo off
chcp 65001 >nul
echo ========================================
echo   全科医生辅助诊断系统 - 启动脚本
echo ========================================
echo.

REM 设置 DeepSeek API Key
set DEEPSEEK_API_KEY=your-deepseek-api-key-here

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python
    pause
    exit /b 1
)

echo [1/3] 安装依赖...
cd /d "%~dp0medrag_backend"
pip install fastapi uvicorn httpx pydantic python-dotenv -q

echo.
echo [2/3] 启动后端服务 (端口 8000)...
start "MedRAG后端" cmd /k "cd /d "%~dp0medrag_backend" && python -c \"import os; os.environ['DEEPSEEK_API_KEY']='your-deepseek-api-key-here'; exec(open('main.py').read())\""

REM 等待后端启动
timeout /t 5 /nobreak >nul

echo [3/3] 启动前端服务 (端口 8080)...
cd /d "%~dp0medrag_frontend"
start "MedRAG前端" cmd /k "python -m http.server 8080"

echo.
echo ========================================
echo   启动完成！
echo ========================================
echo.
echo 请在浏览器中打开: http://localhost:8080
echo.
pause
