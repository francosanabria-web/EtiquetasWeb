@echo off
REM ============================================================================
REM  _start_personal.bat
REM  Lanza el servicio Personal en :8019 (Starlette + MariaDB).
REM ============================================================================
cd /d "%~dp0\..\backend\personal"
set PERSONAL_PORT=8019
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port %PERSONAL_PORT%
