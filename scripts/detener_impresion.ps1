# ============================================================================
#  detener_impresion.ps1
#  Frena TODO: el supervisor y los 3 procesos (API, agente, web).
#  Por defecto NO borra la tarea programada (al proximo inicio de sesion vuelve
#  a arrancar). Usar  -Desinstalar  para tambien quitar el arranque automatico.
#
#  Ej:  powershell -ExecutionPolicy Bypass -File detener_impresion.ps1
#       powershell -ExecutionPolicy Bypass -File detener_impresion.ps1 -Desinstalar
# ============================================================================

param([switch]$Desinstalar)

$ErrorActionPreference = "SilentlyContinue"
$TaskName = "RedImpresionPanol"

function Matar-PorPuerto($port, $nombre) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "Frenado $nombre (PID $($c.OwningProcess), puerto $port)."
  }
}

# 1) Frenar la tarea para que no relance el supervisor mientras limpiamos.
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

# 2) Matar el supervisor (powershell que ejecuta supervisor_impresion.ps1).
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*supervisor_impresion.ps1*" } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Frenado supervisor (PID $($_.ProcessId))."
  }

# 3) Matar el agente de impresion.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*print_agent_api.py*" } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Frenado agente (PID $($_.ProcessId))."
  }

# 4) Matar API (8010) y Web (5173).
Matar-PorPuerto 8010 "API"
Matar-PorPuerto 5173 "Web"

if ($Desinstalar) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Arranque automatico DESINSTALADO (tarea '$TaskName' eliminada)." -ForegroundColor Yellow
} else {
  Write-Host "Listo. (El arranque automatico sigue activo para el proximo inicio de sesion.)" -ForegroundColor Green
}
