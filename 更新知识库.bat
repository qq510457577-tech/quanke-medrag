@echo off
setlocal
set PYTHONUTF8=1

cd /d "%~dp0"

echo ============================================
echo Updating local knowledge drafts...
python medrag_backend\tools\extract_local_references.py
if errorlevel 1 goto :error

echo ============================================
echo Building local RAG vector store...
python medrag_backend\tools\build_vector_store.py
if errorlevel 1 goto :error

echo ============================================
echo Knowledge base update finished.
echo Files folder: %cd%\files
echo Vector store: %cd%\medrag_backend\app\data\vector_store
echo ============================================
pause
exit /b 0

:error
echo.
echo Knowledge base update failed.
pause
exit /b 1
