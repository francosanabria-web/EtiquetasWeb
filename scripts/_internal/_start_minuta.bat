@echo off
REM Helper interno — no ejecutar a mano. Llamado por INICIAR_TODO.bat
cd /d "%~dp0..\backend\minuta_reunion"
if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Minuta...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo Minuta en http://localhost:8013
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8013
pause
