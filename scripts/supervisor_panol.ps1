# ============================================================================
#  supervisor_panol.ps1
#  Mantiene vivos los servicios del portal (NO toca impresion / etiquetas):
#    KPIs :8001 | Minuta :8013 | Solicitudes :8014 | Usuarios :8015
#    Personal :8019 | Cajas :8021 | Activos :8016 | Reportes :8017 | Salidas :8018 | Email :8020 | Portal Vite :5180
#
#  - Idempotente: no duplica si el puerto ya escucha.
#  - Auto-reparable: cada ~20s levanta lo caido; reinicia colgados
#    (puerto abierto pero /health muerto).
#  - Reinicio suave diario: una vez entre 20:00 y 22:00 (hora local).
#  - Corre oculto; logs en scripts\logs\.
#
#  No ejecutar a mano normalmente: tarea "PortalPanol" (instalar_autostart_panol.ps1).
#  Frenar: detener_panol.ps1. Estado: estado_panol.ps1.
#
#  IMPORTANTE: no usar INICIAR_TODO.bat en paralelo (pelea por los mismos puertos).
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"

$Raiz = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

$IntervaloSeg = 20
$ReinicioDesde = 20   # 20:00
$ReinicioHasta = 22   # ventana [20:00, 22:00)
$MarkerReinicio = Join-Path $Logs "panol_reinicio_diario.marker"

$NodeExe = "node"

# --- Definicion de servicios ------------------------------------------------
$Servicios = @(
  @{
    Name = "KPIs"
    Port = 8001
    Health = "http://127.0.0.1:8001/health"
    Accept503 = $true
    Dir = Join-Path $Raiz "backend\kpis"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Minuta"
    Port = 8013
    Health = "http://127.0.0.1:8013/health"
    Accept503 = $false
    Dir = Join-Path $Raiz "backend\minuta_reunion"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Solicitudes"
    Port = 8014
    Health = "http://127.0.0.1:8014/health"
    Accept503 = $false
    Dir = Join-Path $Raiz "backend\solicitudes"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Usuarios"
    Port = 8015
    Health = "http://127.0.0.1:8015/health"
    Accept503 = $false
    Dir = Join-Path $Raiz "backend\usuarios"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Personal"
    Port = 8019
    Health = "http://127.0.0.1:8019/health"
    Accept503 = $false
    Dir = Join-Path $Raiz "backend\personal"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Cajas"
    Port = 8021
    Health = "http://127.0.0.1:8021/health"
    Accept503 = $false
    Dir = Join-Path $Raiz "backend\cajas"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Activos"
    Port = 8016
    Health = "http://127.0.0.1:8016/health"
    Accept503 = $true
    Dir = Join-Path $Raiz "backend\activos"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Reportes"
    Port = 8017
    Health = "http://127.0.0.1:8017/health"
    Accept503 = $true
    Dir = Join-Path $Raiz "backend\reportes"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Salidas"
    Port = 8018
    Health = "http://127.0.0.1:8018/health"
    Accept503 = $true
    Dir = Join-Path $Raiz "backend\salidas"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Email"
    Port = 8020
    Health = "http://127.0.0.1:8020/health"
    Accept503 = $false
    Dir = Join-Path $Raiz "backend\email_service"
    PyRel = ".venv\Scripts\python.exe"
    Uvicorn = "main:app"
  }
  @{
    Name = "Portal"
    Port = 5180
    Health = $null
    Accept503 = $false
    Dir = Join-Path $Raiz "apps\web"
    ViteJs = "node_modules\vite\bin\vite.js"
  }
)

# --- Utilidades -------------------------------------------------------------
function Log($msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path (Join-Path $Logs "supervisor_panol.log") -Value "[$ts] $msg"
  Write-Host "[$ts] $msg" -ForegroundColor Gray
}

function Puerto-Escucha([int]$port) {
  [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Matar-PorPuerto([int]$port, [string]$nombre) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    Log "Frenado $nombre (PID $($c.OwningProcess), puerto $port)."
  }
}

function Health-Estado($svc) {
  # Devuelve: ok | loading | dead | no-health
  if (-not $svc.Health) { return "no-health" }
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 $svc.Health
    if ($r.StatusCode -eq 200) { return "ok" }
    if ($svc.Accept503 -and $r.StatusCode -eq 503) { return "loading" }
    return "dead"
  } catch {
    $msg = "$_"
    if ($svc.Accept503 -and $msg -match "503") { return "loading" }
    return "dead"
  }
}

function Iniciar-Backend($svc) {
  if (Puerto-Escucha $svc.Port) { return }
  $py = Join-Path $svc.Dir $svc.PyRel
  if (-not (Test-Path $py)) {
    Log "SKIP $($svc.Name): no hay venv en $py (crear con _start_*.bat una vez)."
    return
  }
  Log "Iniciando $($svc.Name) (:$($svc.Port))..."
  Write-Host "Iniciando $($svc.Name) (:$($svc.Port))..." -ForegroundColor Yellow
  $out = Join-Path $Logs ("panol_{0}.out.log" -f $svc.Name.ToLower())
  $err = Join-Path $Logs ("panol_{0}.err.log" -f $svc.Name.ToLower())
  Start-Process -FilePath $py `
    -ArgumentList "-m", "uvicorn", $svc.Uvicorn, "--host", "0.0.0.0", "--port", "$($svc.Port)" `
    -WorkingDirectory $svc.Dir -WindowStyle Hidden `
    -RedirectStandardOutput $out -RedirectStandardError $err
}

function Iniciar-Portal($svc) {
  if (Puerto-Escucha $svc.Port) { return }
  $vite = Join-Path $svc.Dir $svc.ViteJs
  Log "Iniciando Portal (:$($svc.Port))..."
  Write-Host "Iniciando Portal (:$($svc.Port))..." -ForegroundColor Yellow
  $out = Join-Path $Logs "panol_portal.out.log"
  $err = Join-Path $Logs "panol_portal.err.log"
  if (Test-Path $vite) {
    Start-Process -FilePath $NodeExe `
      -ArgumentList $vite, "--host", "0.0.0.0", "--port", "$($svc.Port)" `
      -WorkingDirectory $svc.Dir -WindowStyle Hidden `
      -RedirectStandardOutput $out -RedirectStandardError $err
  } else {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "npm run dev" `
      -WorkingDirectory $svc.Dir -WindowStyle Hidden `
      -RedirectStandardOutput $out -RedirectStandardError $err
  }
}

function Reparar-Si-Colgado($svc) {
  if (-not (Puerto-Escucha $svc.Port)) { return }
  if (-not $svc.Health) { return }
  $h = Health-Estado $svc
  if ($h -eq "ok" -or $h -eq "loading") { return }
  Log "$($svc.Name) escucha :$($svc.Port) pero /health muerto - reiniciando."
  Write-Host "Reiniciando $($svc.Name) (:$($svc.Port))..." -ForegroundColor Yellow
  Matar-PorPuerto $svc.Port $svc.Name
  Start-Sleep -Seconds 2
}

function Reinicio-Diario-Pendiente {
  $ahora = Get-Date
  $hora = $ahora.Hour
  if ($hora -lt $ReinicioDesde -or $hora -ge $ReinicioHasta) { return $false }
  $hoy = $ahora.ToString("yyyy-MM-dd")
  if (Test-Path $MarkerReinicio) {
    $prev = (Get-Content $MarkerReinicio -Raw).Trim()
    if ($prev -eq $hoy) { return $false }
  }
  return $true
}

function Ejecutar-Reinicio-Suave {
  Log "=== Reinicio suave diario (ventana $($ReinicioDesde):00-$($ReinicioHasta):00) ==="
  foreach ($svc in $Servicios) {
    Matar-PorPuerto $svc.Port $svc.Name
  }
  Start-Sleep -Seconds 3
  $hoy = (Get-Date).ToString("yyyy-MM-dd")
  Set-Content -Path $MarkerReinicio -Value $hoy -Encoding ASCII
  Log "Reinicio suave marcado para $hoy. El bucle volvera a levantar servicios."
}

# --- Bucle principal --------------------------------------------------------
Log "=== Supervisor portal iniciado (PID $PID) ==="
Write-Host "=== Supervisor Pañol iniciado (PID $PID) ===" -ForegroundColor Cyan
Write-Host "Servicios: KPIs 8001 | Minuta 8013 | Solicitudes 8014 | Usuarios 8015 | Personal 8019 | Cajas 8021 | Activos 8016 | Reportes 8017 | Salidas 8018 | Email 8020 | Portal 5180" -ForegroundColor DarkGray
Write-Host "Logs: $Logs" -ForegroundColor DarkGray
Write-Host "Intervalo: ${IntervaloSeg}s | Reinicio suave: ${ReinicioDesde}:00-${ReinicioHasta}:00" -ForegroundColor DarkGray
while ($true) {
  if (Reinicio-Diario-Pendiente) {
    Ejecutar-Reinicio-Suave
  }

  foreach ($svc in $Servicios) {
    Reparar-Si-Colgado $svc
    if ($svc.Name -eq "Portal") {
      Iniciar-Portal $svc
    } else {
      Iniciar-Backend $svc
    }
  }

  Write-Host "[$(Get-Date -Format HH:mm:ss)] check..." -ForegroundColor DarkGray
  Start-Sleep -Seconds $IntervaloSeg
}
