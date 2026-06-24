@echo off
chcp 65001 >nul
echo ========================================
echo   全科医生辅助诊断系统 - Docker部署
echo ========================================
echo.

REM 检查Docker是否安装
docker --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Docker未安装，请先安装Docker Desktop
    pause
    exit /b 1
)

REM 检查docker-compose是否安装
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [错误] docker-compose未安装
    pause
    exit /b 1
)

echo [1/3] 停止现有容器...
docker-compose down

echo [2/3] 构建并启动容器...
docker-compose up -d --build

echo [3/3] 检查服务状态...
timeout /t 5 /nobreak >nul
docker-compose ps

echo.
echo ========================================
echo   部署完成！
echo ========================================
echo   前端页面: http://localhost
echo   API接口:  http://localhost:8000
echo   API文档:  http://localhost:8000/docs
echo ========================================
echo.
echo 按任意键查看日志...
pause >nul
docker-compose logs -f
