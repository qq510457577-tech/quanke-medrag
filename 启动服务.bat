@echo off
setlocal
set PYTHONUTF8=1

cd /d "%~dp0medrag_backend"

if not exist ".env" (
  echo [Info] medrag_backend\.env not found, using root .env or system environment.
)

echo Starting MedRAG diagnosis backend...
python start_llm.py

endlocal
