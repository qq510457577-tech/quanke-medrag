#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

# 设置工作目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# 设置环境变量
os.environ['DEEPSEEK_API_KEY'] = 'your-deepseek-api-key-here'

# 导入并启动
if __name__ == "__main__":
    import uvicorn
    from main import app
    
    print("=" * 50)
    print("全科医生辅助诊断系统 - 后端服务")
    print("API 文档：http://localhost:8000/docs")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
