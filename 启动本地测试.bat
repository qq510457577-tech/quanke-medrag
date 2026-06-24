@echo off
chcp 65001 >nul
echo ========================================
echo   全科医生辅助诊断系统 - 启动脚本
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查 pip 是否可用
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 pip，请先安装 pip
    pause
    exit /b 1
)

REM 安装后端依赖
echo [1/4] 安装后端依赖...
cd /d "%~dp0medrag_backend"
pip install fastapi uvicorn httpx pydantic python-dotenv -q
if %errorlevel% neq 0 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)
echo.

REM 检查 DeepSeek API Key
echo [2/4] 检查环境变量...
if not defined DEEPSEEK_API_KEY (
    echo [警告] 未设置 DEEPSEEK_API_KEY 环境变量
    echo 请在运行前设置环境变量：
    echo   Windows: set DEEPSEEK_API_KEY=your_api_key
    echo   或在 .env 文件中配置
    echo.
)

REM 启动后端服务
echo [3/4] 启动后端服务...
start "MedRAG后端服务" cmd /k "cd /d "%~dp0medrag_backend" && python main.py"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端（使用 Python 内置 HTTP 服务器）
echo [4/4] 启动前端服务...
cd /d "%~dp0medrag_frontend"
start "MedRAG前端服务" cmd /k "python -m http.server 8080"

echo.
echo ========================================
echo   启动完成！
echo ========================================
echo.
echo 后端 API: http://localhost:8000
echo 前端页面: http://localhost:8080
echo API 文档: http://localhost:8000/docs
echo.
echo 按任意键打开浏览器...
pause >nul

start http://localhost:8080
