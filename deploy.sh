#!/bin/bash
# 全科医生辅助诊断系统 - Docker部署脚本 (Linux/Mac)

echo "========================================"
echo "  全科医生辅助诊断系统 - Docker部署"
echo "========================================"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "[错误] Docker未安装，请先安装Docker Desktop"
    exit 1
fi

# 检查docker-compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "[错误] docker-compose未安装"
    exit 1
fi

echo "[1/3] 停止现有容器..."
docker-compose down

echo "[2/3] 构建并启动容器..."
docker-compose up -d --build

echo "[3/3] 检查服务状态..."
sleep 5
docker-compose ps

echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo "  前端页面: http://localhost"
echo "  API接口:  http://localhost:8000"
echo "  API文档:  http://localhost:8000/docs"
echo "========================================"
echo ""
echo "查看日志: docker-compose logs -f"
echo "停止服务: docker-compose down"
