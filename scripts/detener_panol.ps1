# ============================================================================
#  detener_panol.ps1
#  Frena el supervisor del portal y los servicios :8001 :8013 :8014 :8015
#  :8016 :8017 :8018 :8020 :5180. NO toca impresion (8010 / 5173 / print-agent).
#
#  Por defecto NO borra la tarea PortalPanol.
#  Usar -Desinstalar para quitar el arranque automatico.
#
#  Ej:  powershell -ExecutionPolicy Bypass -File detener_panol.ps1
#       powershell -ExecutionPolicy Bypass -File detener_panol.ps1 -Desinstalar
# ============================================================================

param([switch]$Desinstalar)

$ErrorActionPreference = "SilentlyContinue"
$TaskName = "PortalPanol"

function Matar-PorPuerto([int]$port, [string]$nombre) {
  $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
  foreach ($c in $conns) {
    Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "Frenado $nombre (PID $($c.OwningProcess), puerto $port)."
  }
}

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*supervisor_panol.ps1*" } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Host "Frenado supervisor portal (PID $($_.ProcessId))."
  }

Matar-PorPuerto 8001 "KPIs"
Matar-PorPuerto 8013 "Minuta"
Matar-PorPuerto 8014 "Solicitudes"
Matar-PorPuerto 8015 "Usuarios"
Matar-PorPuerto 8016 "Activos"
Matar-PorPuerto 8017 "Reportes"
Matar-PorPuerto 8018 "Salidas"
Matar-PorPuerto 8019 "Personal"
Matar-PorPuerto 8021 "Cajas"
Matar-PorPuerto 8020 "Email"
Matar-PorPuerto 5180 "Portal"

if ($Desinstalar) {
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Arranque automatico DESINSTALADO (tarea '$TaskName' eliminada)." -ForegroundColor Yellow
} else {
  Write-Host "Listo. (El arranque automatico sigue activo para el proximo inicio de sesion.)" -ForegroundColor Green
}
