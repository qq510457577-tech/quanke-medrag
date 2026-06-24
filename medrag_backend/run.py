import os
os.environ['DEEPSEEK_API_KEY'] = 'your-deepseek-api-key-here'

import uvicorn
from main import app

if __name__ == "__main__":
    print("=" * 50)
    print("全科医生辅助诊断系统 - 后端服务")
    print("API 文档：http://localhost:8000/docs")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
