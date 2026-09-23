@echo off
REM Helper interno — llamado por INICIAR_TODO.bat / supervisor
cd /d "%~dp0..\backend\salidas"

REM Planta: lee master_codes (solo lectura) y escribe en salidas_web.
REM Doble espacio en "MANTENIMIENTO  OZLA" — no quitar.
set "SALIDAS_PANOL_PATH=G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"
set "SALIDAS_MAESTRO_PATH=%SALIDAS_PANOL_PATH%\master_codes.xlsx"
set "SALIDAS_WEB_PATH=%SALIDAS_PANOL_PATH%\salidas_web"
REM No escribir Firestore al confirmar (decisión 2026-08-05)
set "SALIDAS_FIREBASE_WRITE=0"
REM Punto 2 - DB directo MariaDB panol.s salida_historial (bajas en vivo)
REM 1 = escribe directo a DB, 0 = modo Excel (legacy). Para volver a Excel: set "SALIDAS_DB_ENABLED=0"
set "SALIDAS_DB_ENABLED=1"
REM 0 = solo DB (recomendado), 1 = dual-write DB+Excel (backup transitorio si necesitas trazar Excel)
set "SALIDAS_EXCEL_BACKUP=0"

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual Salidas...
  python -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo Salidas (egreso material) en http://localhost:8018
echo Maestro (lectura): %SALIDAS_MAESTRO_PATH%
echo Escritura:         %SALIDAS_WEB_PATH%
if "%SALIDAS_DB_ENABLED%"=="1" (
  echo Modo DB:           MariaDB panol.salida_historial ^(DB directo, bajas en vivo^)
) else (
  echo Modo DB:           Excel fallback ^(SALIDAS_DB_ENABLED=0^)
)
if "%SALIDAS_EXCEL_BACKUP%"=="1" echo Backup Excel:     dual-write DB+Excel activo
echo.
".venv\Scripts\python.exe" -m uvicorn main:app --host 0.0.0.0 --port 8018
pause
