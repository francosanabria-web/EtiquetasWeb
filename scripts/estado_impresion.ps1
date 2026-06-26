# ============================================================================
#  estado_impresion.ps1
#  Muestra de un vistazo si los 3 servicios estan arriba y la tarea programada.
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"
$TaskName = "RedImpresionPanol"
$Logs = Join-Path $PSScriptRoot "logs"

function Estado-Puerto($port) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { "ARRIBA" } else { "CAIDO" }
}

Write-Host "==== Estado red de impresion ===="

# API
$api = "CAIDO"
try { if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 "http://127.0.0.1:8010/health").StatusCode -eq 200) { $api = "ARRIBA" } } catch {}
Write-Host ("  API (8010) ........ {0}" -f $api)

# Web
Write-Host ("  Web (5173) ........ {0}" -f (Estado-Puerto 5173))

# Agente
$agt = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -like "*print_agent_api.py*" }
Write-Host ("  Agente impresion .. {0}" -f $(if ($agt) { "ARRIBA (PID $($agt.ProcessId -join ','))" } else { "CAIDO" }))

# Supervisor
$sup = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -like "*supervisor_impresion.ps1*" }
Write-Host ("  Supervisor ........ {0}" -f $(if ($sup) { "ARRIBA (PID $($sup.ProcessId -join ','))" } else { "CAIDO" }))

# Tarea programada
$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Write-Host ("  Tarea autostart ... {0}" -f $(if ($t) { $t.State } else { "NO INSTALADA" }))

if (Test-Path (Join-Path $Logs "supervisor.log")) {
  Write-Host "`n-- Ultimas lineas del supervisor --"
  Get-Content (Join-Path $Logs "supervisor.log") -Tail 6
}
