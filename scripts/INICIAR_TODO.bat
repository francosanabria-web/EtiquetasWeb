@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0.."
set "SCRIPTS=%~dp0"

title Sistemas Panol - Arranque completo

echo.
echo ============================================================
echo   SISTEMAS PANOL - Arranque completo (un solo .bat)
echo ============================================================
echo.

REM --- IP local (para acceso desde otra PC) ---
set "IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  set "IP=%%a"
  goto :gotip
)
:gotip
set "IP=%IP: =%"
if not defined IP set "IP=localhost"

echo IP de esta PC: %IP%
echo.

REM --- Liberar puertos si quedaron colgados ---
echo [0/6] Liberando puertos si estaban ocupados...
for %%P in (8001 8013 8014 8020 5180) do (
  for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%%P " ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
  )
)
timeout /t 2 /nobreak >nul

REM --- Backends (ventanas separadas; no cerrar mientras use el portal) ---
echo [1/6] KPIs (puerto 8001) - Excel en G: puede tardar 1-2 min...
start "Panol-KPIs" cmd /k "%SCRIPTS%_start_kpis.bat"

echo [2/6] Minuta SQLite (puerto 8013)...
start "Panol-Minuta" cmd /k "%SCRIPTS%_start_minuta.bat"

echo [3/6] Correo (puerto 8020)...
start "Panol-Email" cmd /k "%SCRIPTS%_start_email.bat"

echo [4/6] Solicitud de pedidos (puerto 8014)...
start "Panol-Solicitudes" cmd /k "%SCRIPTS%_start_solicitudes.bat"

echo.
echo Esperando que KPIs / Minuta / Email / Solicitudes respondan...
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPTS%esperar_servicios.ps1"
if errorlevel 1 (
  echo.
  echo AVISO: algun backend no respondio a tiempo.
  echo Revise las ventanas Panol-KPIs / Panol-Minuta / Panol-Email / Panol-Solicitudes.
  echo (Unidad G: montada?)
  echo.
)

echo [5/6] Portal web (puerto 5180)...
start "Panol-Portal" cmd /k "%SCRIPTS%_start_portal.bat"

echo [6/6] Esperando portal...
timeout /t 6 /nobreak >nul

echo.
echo ============================================================
echo   LISTO - Abrir en el navegador
echo ============================================================
echo.
echo   PORTAL (esta PC):     http://localhost:5180
echo   PORTAL (otra PC):     http://%IP%:5180
echo.
echo   Modulos:
echo     Inicio:                 http://localhost:5180/
echo     KPIs:                   http://localhost:5180/kpis
echo     Minuta de reunion:      http://localhost:5180/minuta
echo     Solicitud de pedidos:   http://localhost:5180/solicitudes
echo     Activos fuera planta:   http://localhost:5180/activos
echo.
echo   Login demo:
echo     Jefatura:   jefatura@panol.local   / jefatura123
echo     Admin:      admin@panol.local      / admin123
echo     Panol:      panol@panol.local      / panol123
echo     Supervisor: supervisor@panol.local / supervisor123
echo.
echo   Requisitos:
echo     - Unidad G: montada (Excel del panol)
echo     - Firewall: permitir 5180 si entran desde otra PC
echo.
echo   Ventanas abiertas (no cerrar mientras use el portal):
echo     Panol-KPIs  ^|  Panol-Minuta  ^|  Panol-Email  ^|  Panol-Solicitudes  ^|  Panol-Portal
echo ============================================================
echo.
pause
endlocal
