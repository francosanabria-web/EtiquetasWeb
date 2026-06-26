# ============================================================================
#  supervisor_impresion.ps1
#  Mantiene vivos los 3 procesos de la red de impresion de etiquetas:
#    1) API        (uvicorn / etiquetas-api)   -> puerto 8010
#    2) Agente     (print_agent_api.py)         -> imprime
#    3) Web        (vite / etiquetas-web)       -> puerto 5173
#
#  - Es IDEMPOTENTE: nunca duplica procesos (chequea puertos y linea de comando).
#  - Es AUTO-REPARABLE: si alguno se cae, lo vuelve a levantar.
#  - Corre OCULTO y deja logs en scripts\logs\.
#
#  No ejecutar a mano normalmente: lo lanza la tarea programada al iniciar sesion
#  (ver instalar_autostart.ps1). Para frenar todo: detener_impresion.ps1.
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"

# --- Rutas ------------------------------------------------------------------
$Raiz   = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Raiz "services\etiquetas-api"
$AgtDir = Join-Path $Raiz "services\print-agent"
$WebDir = Join-Path $Raiz "services\etiquetas-web"
$Logs   = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

$PyApi = Join-Path $ApiDir ".venv\Scripts\python.exe"

# Python del agente (el global, que tiene Pillow/qrcode/pywin32).
$PyAgt = "C:\Users\Mantenimiento\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if (-not (Test-Path $PyAgt)) { $PyAgt = "py" }

# Vite directo por node (evita el wrapper npm.cmd).
$NodeExe = "node"
$ViteJs  = Join-Path $WebDir "node_modules\vite\bin\vite.js"

$ApiUrl    = "http://127.0.0.1:8010"
$ApiPort   = 8010
$WebPort   = 5173
$IntervaloSeg = 20

# --- Utilidades -------------------------------------------------------------
function Log($msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path (Join-Path $Logs "supervisor.log") -Value "[$ts] $msg"
}

function Puerto-Escucha($port) {
  [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Api-Viva {
  try {
    (Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 "$ApiUrl/health").StatusCode -eq 200
  } catch { $false }
}

function Agente-Corriendo {
  $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
           Where-Object { $_.CommandLine -like "*print_agent_api.py*" }
  [bool]$procs
}

# --- Arranque de cada servicio (solo si no esta corriendo) ------------------
function Iniciar-Api {
  if (Puerto-Escucha $ApiPort) { return }
  Log "Iniciando API..."
  Start-Process -FilePath $PyApi `
    -ArgumentList "-m","uvicorn","main:app","--host","0.0.0.0","--port","$ApiPort" `
    -WorkingDirectory $ApiDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Logs "api.out.log") `
    -RedirectStandardError  (Join-Path $Logs "api.err.log")
}

function Iniciar-Agente {
  if (Agente-Corriendo) { return }
  Log "Iniciando agente de impresion..."
  Start-Process -FilePath $PyAgt `
    -ArgumentList "print_agent_api.py","--api",$ApiUrl `
    -WorkingDirectory $AgtDir -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $Logs "agente.out.log") `
    -RedirectStandardError  (Join-Path $Logs "agente.err.log")
}

function Iniciar-Web {
  if (Puerto-Escucha $WebPort) { return }
  Log "Iniciando web..."
  if (Test-Path $ViteJs) {
    Start-Process -FilePath $NodeExe -ArgumentList $ViteJs `
      -WorkingDirectory $WebDir -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $Logs "web.out.log") `
      -RedirectStandardError  (Join-Path $Logs "web.err.log")
  } else {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c","npm run dev" `
      -WorkingDirectory $WebDir -WindowStyle Hidden `
      -RedirectStandardOutput (Join-Path $Logs "web.out.log") `
      -RedirectStandardError  (Join-Path $Logs "web.err.log")
  }
}

# --- Bucle principal --------------------------------------------------------
Log "=== Supervisor iniciado (PID $PID) ==="
while ($true) {
  Iniciar-Api
  if (Api-Viva) { Iniciar-Agente }   # el agente necesita la API arriba
  Iniciar-Web
  Start-Sleep -Seconds $IntervaloSeg
}
