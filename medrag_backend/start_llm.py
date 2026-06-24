"""
全科医生辅助诊断系统 - 启动脚本
版本：2.0.0 (DeepSeek-V3.2-Speciale LLM版)
"""

import os
import sys

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("   全科医生辅助诊断系统")
    print("   基于 DeepSeek-V3.2-Speciale API 实现 LLM临床思维链")
    print("=" * 60)
    print()
    print("服务地址：http://localhost:8000")
    print("API文档：http://localhost:8000/docs")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    
    uvicorn.run(
        "llm_diagnosis:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
