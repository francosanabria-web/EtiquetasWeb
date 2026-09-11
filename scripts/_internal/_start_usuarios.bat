@echo off
REM Helper interno — llamado por INICIAR_TODO.bat
cd /d "%~dp0..\backend\usuarios"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Usuarios...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo Usuarios / accesos en http://localhost:8015
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8015
pause
