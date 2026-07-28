@echo off
REM Helper interno — no ejecutar a mano. Llamado por INICIAR_TODO.bat
cd /d "%~dp0..\backend\email_service"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Email...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo Email en http://localhost:8020
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8020
pause
