@echo off
cd /d "%~dp0medrag_backend"
echo Starting server...
python -m uvicorn llm_diagnosis:app --host 0.0.0.0 --port 8000
