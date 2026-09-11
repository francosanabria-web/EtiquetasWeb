@echo off
REM ============================================================================
REM  _start_cajas.bat
REM  Lanza el servicio Cajas en :8021 (Starlette + MariaDB).
REM ============================================================================
cd /d "%~dp0\..\backend\cajas"
set CAJAS_PORT=8021
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port %CAJAS_PORT%
