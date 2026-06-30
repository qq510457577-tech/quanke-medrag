import os
import sys

import uvicorn


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


if __name__ == "__main__":
    print("=" * 60)
    print("General Practice MedRAG Backend")
    print("Service: http://127.0.0.1:8000")
    print("Health : http://127.0.0.1:8000/api/health")
    print("Docs   : http://127.0.0.1:8000/docs")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
