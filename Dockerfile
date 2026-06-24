# 全科医生辅助诊断系统 - Docker镜像
# 基于MedRAG + DeepSeek API实现循证医学临床思维链辅助诊断

# 阶段1: Python后端构建
FROM python:3.10-slim as backend

WORKDIR /app

# 安装后端依赖
COPY medrag_backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY medrag_backend/llm_diagnosis.py .
COPY medrag_backend/start_llm.py .

# 阶段2: Nginx前端构建
FROM nginx:alpine as frontend

# 复制前端文件
COPY medrag_frontend/llm_index.html /usr/share/nginx/html/index.html

# 阶段3: 生产镜像
FROM python:3.10-slim

# 安装nginx和supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY:-sk-5c8e622180db4be792584b4c814343d2}

# 创建目录
RUN mkdir -p /app /var/log/supervisor

# 复制后端文件
COPY --from=backend /app /app

# 复制前端文件
COPY --from=frontend /usr/share/nginx/html /usr/share/nginx/html

# 复制nginx配置
COPY docker/nginx.conf /etc/nginx/nginx.conf

# 复制supervisor配置
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 暴露端口
EXPOSE 80 8000

# 启动supervisor
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
