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
#
#  FIX 2026-09-18: Salidas quedaba colgado / loop infinito Iniciando Salidas.
#    Causa raiz: venv de salidas sin pymysql/python-jose -> crash inmediato,
#    puerto nunca abre, supervisor reintentaba cada 20s sin backoff ni diagnostico.
#    Este parche:
#      - Health via HttpClient (evita cuelgue de Invoke-WebRequest en PS5.1)
#      - Cooldown 45s entre reintentos del mismo puerto caido
#      - Gracia 35s tras arranque antes de declarar /health muerto
#      - Deteccion de crash inmediato (HasExited) con tail de .err.log en supervisor.log
#      - Rate-limit de SKIP para no inundar logs
#      - Marcadores .starting para no spawnear duplicado mientras uvicorn bindea
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"
try { Add-Type -AssemblyName System.Net.Http -ErrorAction SilentlyContinue } catch {}

$Raiz = Split-Path -Parent $PSScriptRoot
$Logs = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

# Punto 2 - Salidas DB directo MariaDB (bajas en vivo). Debe quedar activo para que :8018 registre en panol.salida_historial.
# Si necesitas volver a Excel solo: cambiar a "0" y reiniciar supervisor (ver _start_salidas.bat para modo manual).
$env:SALIDAS_DB_ENABLED = "1"
$env:SALIDAS_EXCEL_BACKUP = "0"
$env:SALIDAS_FIREBASE_WRITE = "0"
# Opcional: forzar ruta panol si Drive cambia de letra (dejar comentado si G: es correcto)
# $env:SALIDAS_PANOL_PATH = "G:\Unidades compartidas\Mantenimiento\MANTENIMIENTO  OZLA 2024-2025\17. Pañol\pañol v5.0"

# Evitar dos supervisores peleando por los mismos puertos (esa race dejaba Reportes colgado)
$global:SupervisorMutex = $null
try {
  $global:SupervisorMutex = New-Object System.Threading.Mutex($false, "Global\PortalPanolSupervisor_v1")
  if (-not $global:SupervisorMutex.WaitOne(0)) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $msg = "[$ts] Otro supervisor ya corre - este PID $PID sale sin tocar servicios."
    try { Add-Content -Path (Join-Path $Logs "supervisor_panol.log") -Value $msg -ErrorAction SilentlyContinue } catch {}
    Write-Host $msg -ForegroundColor Yellow
    exit 0
  }
} catch {}

$IntervaloSeg = 20
$ReinicioDesde = 20   # 20:00
$ReinicioHasta = 22   # ventana [20:00, 22:00)
$MarkerReinicio = Join-Path $Logs "panol_reinicio_diario.marker"

$NodeExe = "node"

# Cooldown y gracia para evitar loop/asesinato prematuro
$CooldownSeg = 45    # no reintentar mismo servicio caido antes de 45s
$GraceSeg = 35       # tras arrancar, dar 35s antes de matar por /health muerto
$global:UltimoInicio = @{}    # Port -> DateTime ultimo Start-Process
$global:UltimoFalloLog = @{}  # "skip_8018" -> DateTime ultimo SKIP log

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
  $line = "[$ts] $msg"
  try { Add-Content -Path (Join-Path $Logs "supervisor_panol.log") -Value $line -ErrorAction SilentlyContinue } catch {}
  Write-Host $line -ForegroundColor Gray
}

function Get-ErrorTail([string]$path, [int]$lines = 12) {
  try {
    if (-not (Test-Path -LiteralPath $path -ErrorAction SilentlyContinue)) { return "" }
    $txt = (Get-Content -LiteralPath $path -Tail $lines -ErrorAction SilentlyContinue | Out-String).Trim()
    if (-not $txt) { return "" }
    $txt = $txt -replace "`r`n", " | " -replace "`n", " | "
    if ($txt.Length -gt 420) { $txt = $txt.Substring(0, 420) + "..." }
    return $txt
  } catch { return "" }
}

function Puerto-Escucha([int]$port) {
  try {
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return [bool]$c
  } catch { return $false }
}

function Matar-PorPuerto([int]$port, [string]$nombre) {
  try {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
      try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
      Log "Frenado $nombre (PID $($c.OwningProcess), puerto $port)."
    }
  } catch {}
  $marker = Join-Path $Logs ("panol_{0}.starting" -f $nombre.ToLower())
  if (Test-Path $marker) { Remove-Item -LiteralPath $marker -Force -ErrorAction SilentlyContinue }
}

function Health-Estado($svc) {
  if (-not $svc.Health) { return "no-health" }
  $client = $null
  $handler = $null
  try {
    $handler = New-Object System.Net.Http.HttpClientHandler -ErrorAction Stop
    $handler.UseProxy = $false
    $client = New-Object System.Net.Http.HttpClient($handler) -ErrorAction Stop
    $client.Timeout = [TimeSpan]::FromSeconds(3.5)
    $task = $client.GetAsync($svc.Health)
    if (-not $task.Wait(4000)) { return "dead" }
    $resp = $task.Result
    if (-not $resp) { return "dead" }
    $code = [int]$resp.StatusCode
    try { $resp.Dispose() } catch {}
    if ($code -eq 200) { return "ok" }
    if ($svc.Accept503 -and $code -eq 503) { return "loading" }
    return "dead"
  } catch {
    # Fallback a Invoke-WebRequest si HttpClient no esta disponible
    try {
      $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 $svc.Health -ErrorAction Stop
      if ($r.StatusCode -eq 200) { return "ok" }
      if ($svc.Accept503 -and $r.StatusCode -eq 503) { return "loading" }
      return "dead"
    } catch {
      $msg = "$_"
      if ($svc.Accept503 -and $msg -match "503") { return "loading" }
      return "dead"
    }
  } finally {
    try { if ($client) { $client.Dispose() } } catch {}
    try { if ($handler) { $handler.Dispose() } } catch {}
  }
}

function Iniciar-Backend($svc) {
  if (Puerto-Escucha $svc.Port) { return }
  $py = Join-Path $svc.Dir $svc.PyRel
  if (-not (Test-Path -LiteralPath $py -ErrorAction SilentlyContinue)) {
    $key = "skip_$($svc.Port)"
    $ahora = Get-Date
    $last = $global:UltimoFalloLog[$key]
    if (-not $last -or ($ahora - $last).TotalSeconds -gt 300) {
      Log "SKIP $($svc.Name): no hay venv en $py (crear con _start_*.bat una vez)."
      $global:UltimoFalloLog[$key] = $ahora
    }
    return
  }
  if (-not (Test-Path -LiteralPath $svc.Dir -ErrorAction SilentlyContinue)) {
    Log "SKIP $($svc.Name): falta directorio $($svc.Dir)"
    return
  }
  # Cooldown: si falló hace < CooldownSeg, no spamear Start-Process
  $key = "$($svc.Port)"
  $ahora = Get-Date
  if ($global:UltimoInicio.ContainsKey($key)) {
    $elapsed = ($ahora - $global:UltimoInicio[$key]).TotalSeconds
    if ($elapsed -lt $CooldownSeg) { return }
  }

  # Zombies que bloquean logs: matar python --port X que no escuchan (quedan huérfanos del loop anterior)
  try {
    $zombies = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*--port $($svc.Port)*" }
    if ($zombies) {
      foreach ($z in $zombies) { try { Stop-Process -Id $z.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
      Start-Sleep -Milliseconds 600
    }
  } catch {}

  Log "Iniciando $($svc.Name) (:$($svc.Port))..."
  Write-Host "Iniciando $($svc.Name) (:$($svc.Port))..." -ForegroundColor Yellow
  $out = Join-Path $Logs ("panol_{0}.out.log" -f $svc.Name.ToLower())
  $err = Join-Path $Logs ("panol_{0}.err.log" -f $svc.Name.ToLower())
  $starting = Join-Path $Logs ("panol_{0}.starting" -f $svc.Name.ToLower())

  # Rotar o liberar logs bloqueados (zombies los dejan con handle abierto)
  try {
    foreach ($p in @($out, $err)) {
      if (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue) {
        $sz = (Get-Item -LiteralPath $p -ErrorAction SilentlyContinue).Length
        if ($sz -gt 2MB) {
          try { Remove-Item -LiteralPath $p -Force -ErrorAction Stop } catch {
            try { Move-Item -LiteralPath $p -Destination "$p.old" -Force -ErrorAction SilentlyContinue } catch {}
          }
        } else {
          # si el archivo sigue bloqueado, renombrar para que Start-Process pueda crear uno nuevo
          try { $fs=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None); $fs.Close() } catch {
            try { Move-Item -LiteralPath $p -Destination "$p.old" -Force -ErrorAction SilentlyContinue } catch {}
          }
        }
      }
    }
  } catch {}

  try { Set-Content -LiteralPath $starting -Value ($ahora.ToString("o")) -Force -ErrorAction SilentlyContinue } catch {}
  $global:UltimoInicio[$key] = $ahora

  # Punto 2 - asegurar env Salidas DB directo aun si supervisor fue iniciado con perfil viejo
  if ($svc.Name -eq "Salidas") {
    $env:SALIDAS_DB_ENABLED = "1"
    $env:SALIDAS_EXCEL_BACKUP = "0"
    $env:SALIDAS_FIREBASE_WRITE = "0"
  }

  $proc = $null
  try {
    $proc = Start-Process -FilePath $py `
      -ArgumentList @("-m", "uvicorn", $svc.Uvicorn, "--host", "0.0.0.0", "--port", "$($svc.Port)") `
      -WorkingDirectory $svc.Dir -WindowStyle Hidden `
      -RedirectStandardOutput $out -RedirectStandardError $err -PassThru -ErrorAction Stop
  } catch {
    Log "FALLO spawn $($svc.Name) : $_"
    return
  }

  Start-Sleep -Milliseconds 1800
  try {
    if ($proc -and $proc.HasExited) {
      $code = $proc.ExitCode
      $tail = Get-ErrorTail $err 14
      if (-not $tail) { $tail = Get-ErrorTail $out 8 }
      if ($tail) {
        Log "FALLO $($svc.Name) salio inmediato (exit $code) :$($svc.Port) -> $tail"
      } else {
        Log "FALLO $($svc.Name) salio inmediato (exit $code) :$($svc.Port) (ver $err)"
      }
      return
    }
  } catch {}
}

function Iniciar-Portal($svc) {
  if (Puerto-Escucha $svc.Port) { return }
  $key = "$($svc.Port)"
  $ahora = Get-Date
  if ($global:UltimoInicio.ContainsKey($key)) {
    $elapsed = ($ahora - $global:UltimoInicio[$key]).TotalSeconds
    if ($elapsed -lt $CooldownSeg) { return }
  }
  # Limpiar zombies vite que dejan el log bloqueado (habia 4 vivos del 10/09)
  try {
    $zombies = Get-CimInstance Win32_Process -Filter "Name='node.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*--port 5180*" -or $_.CommandLine -like "*vite.js*5180*" }
    # matar los que no son el que escucha (como no escucha, todos son zombies en este punto)
    if ($zombies) {
      foreach ($z in $zombies) { try { Stop-Process -Id $z.ProcessId -Force -ErrorAction SilentlyContinue } catch {} }
      Start-Sleep -Milliseconds 700
    }
  } catch {}
  $vite = Join-Path $svc.Dir $svc.ViteJs
  Log "Iniciando Portal (:$($svc.Port))..."
  Write-Host "Iniciando Portal (:$($svc.Port))..." -ForegroundColor Yellow
  $out = Join-Path $Logs "panol_portal.out.log"
  $err = Join-Path $Logs "panol_portal.err.log"
  $starting = Join-Path $Logs "panol_portal.starting"
  try {
    foreach ($p in @($out, $err)) {
      if (Test-Path -LiteralPath $p -ErrorAction SilentlyContinue) {
        $sz = (Get-Item -LiteralPath $p -ErrorAction SilentlyContinue).Length
        if ($sz -gt 2MB) {
          try { Remove-Item -LiteralPath $p -Force -ErrorAction Stop } catch {
            try { Move-Item -LiteralPath $p -Destination "$p.old" -Force -ErrorAction SilentlyContinue } catch {}
          }
        } else {
          try { $fs=[IO.File]::Open($p,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None); $fs.Close() } catch {
            try { Move-Item -LiteralPath $p -Destination "$p.old" -Force -ErrorAction SilentlyContinue } catch {}
          }
        }
      }
    }
  } catch {}
  try { Set-Content -LiteralPath $starting -Value ($ahora.ToString("o")) -Force -ErrorAction SilentlyContinue } catch {}
  $global:UltimoInicio[$key] = $ahora
  try {
    if (Test-Path -LiteralPath $vite -ErrorAction SilentlyContinue) {
      Start-Process -FilePath $NodeExe `
        -ArgumentList @($vite, "--host", "0.0.0.0", "--port", "$($svc.Port)") `
        -WorkingDirectory $svc.Dir -WindowStyle Hidden `
        -RedirectStandardOutput $out -RedirectStandardError $err -ErrorAction Stop | Out-Null
    } else {
      Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "npm run dev") `
        -WorkingDirectory $svc.Dir -WindowStyle Hidden `
        -RedirectStandardOutput $out -RedirectStandardError $err -ErrorAction Stop | Out-Null
    }
  } catch {
    Log "FALLO spawn Portal : $_"
  }
}

function Reparar-Si-Colgado($svc) {
  if (-not (Puerto-Escucha $svc.Port)) { return }
  if (-not $svc.Health) { return }
  # Gracia tras arranque: no matar si hace < GraceSeg que se lanzo (evita matar Salidas mientras carga G:/Excel)
  $key = "$($svc.Port)"
  if ($global:UltimoInicio.ContainsKey($key)) {
    $elapsed = ((Get-Date) - $global:UltimoInicio[$key]).TotalSeconds
    if ($elapsed -lt $GraceSeg) { return }
  }
  $h = $null
  try { $h = Health-Estado $svc } catch { $h = "dead" }
  if ($h -eq "ok" -or $h -eq "loading") { return }
  $tail = Get-ErrorTail (Join-Path $Logs ("panol_{0}.err.log" -f $svc.Name.ToLower())) 6
  if ($tail) {
    Log "$($svc.Name) escucha :$($svc.Port) pero /health muerto ($h) - reiniciando. err: $tail"
  } else {
    Log "$($svc.Name) escucha :$($svc.Port) pero /health muerto ($h) - reiniciando."
  }
  Write-Host "Reiniciando $($svc.Name) (:$($svc.Port))..." -ForegroundColor Yellow
  Matar-PorPuerto $svc.Port $svc.Name
  Start-Sleep -Seconds 2
}

function Reinicio-Diario-Pendiente {
  $ahora = Get-Date
  $hora = $ahora.Hour
  if ($hora -lt $ReinicioDesde -or $hora -ge $ReinicioHasta) { return $false }
  $hoy = $ahora.ToString("yyyy-MM-dd")
  if (Test-Path -LiteralPath $MarkerReinicio -ErrorAction SilentlyContinue) {
    try { $prev = (Get-Content -LiteralPath $MarkerReinicio -Raw -ErrorAction SilentlyContinue).Trim() } catch { $prev = "" }
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
  try { Set-Content -LiteralPath $MarkerReinicio -Value $hoy -Encoding ASCII -ErrorAction SilentlyContinue } catch {}
  # limpiar cooldown para que el bucle los levante de inmediato tras reinicio
  $global:UltimoInicio.Clear()
  Log "Reinicio suave marcado para $hoy. El bucle volvera a levantar servicios."
}

# --- Bucle principal --------------------------------------------------------
Log "=== Supervisor portal iniciado (PID $PID) ==="
Write-Host "=== Supervisor Pañol iniciado (PID $PID) ===" -ForegroundColor Cyan
Write-Host "Servicios: KPIs 8001 | Minuta 8013 | Solicitudes 8014 | Usuarios 8015 | Personal 8019 | Cajas 8021 | Activos 8016 | Reportes 8017 | Salidas 8018 | Email 8020 | Portal 5180" -ForegroundColor DarkGray
Write-Host "Logs: $Logs" -ForegroundColor DarkGray
Write-Host "Intervalo: ${IntervaloSeg}s | Reinicio suave: ${ReinicioDesde}:00-${ReinicioHasta}:00 | Cooldown: ${CooldownSeg}s Grace: ${GraceSeg}s" -ForegroundColor DarkGray
while ($true) {
  try {
    if (Reinicio-Diario-Pendiente) {
      Ejecutar-Reinicio-Suave
    }

    foreach ($svc in $Servicios) {
      try {
        Reparar-Si-Colgado $svc
        if ($svc.Name -eq "Portal") {
          Iniciar-Portal $svc
        } else {
          Iniciar-Backend $svc
        }
      } catch {
        Log "WARN loop $($svc.Name): $_"
      }
    }
  } catch {
    Log "WARN ciclo supervisor: $_"
  }

  Write-Host "[$(Get-Date -Format HH:mm:ss)] check..." -ForegroundColor DarkGray
  Start-Sleep -Seconds $IntervaloSeg
}
