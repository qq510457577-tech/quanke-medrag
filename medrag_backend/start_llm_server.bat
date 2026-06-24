@echo off
cd /d "%~dp0"
echo Starting LLM Diagnosis Server...
python -m uvicorn llm_diagnosis:app --host 0.0.0.0 --port 8000 --reload
echo Server started. Press Ctrl+C to stop.
pause
