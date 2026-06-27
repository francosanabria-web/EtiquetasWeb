# ============================================================================
#  monitoreo_salud.ps1
#  Chequeo PASIVO de la red de impresion. NO reinicia ni modifica nada.
#  Solo consulta puertos/health y escribe en scripts\logs\monitoreo.log.
#
#  Para ejecutarlo cada 5 minutos (opcional, tras instalar_autostart):
#    powershell -ExecutionPolicy Bypass -File scripts\instalar_monitoreo.ps1
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"
$Logs = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null
$LogFile = Join-Path $Logs "monitoreo.log"

function Log($msg) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -Path $LogFile -Value "[$ts] $msg"
}

$api = "CAIDO"
try {
  if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 "http://127.0.0.1:8010/health").StatusCode -eq 200) {
    $api = "OK"
  }
} catch {}

$web = if (Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue) { "OK" } else { "CAIDO" }
$agt = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
       Where-Object { $_.CommandLine -like "*print_agent_api.py*" }
$agtSt = if ($agt) { "OK" } else { "CAIDO" }

$linea = "API=$api | Web=$web | Agente=$agtSt"
Log $linea

# Solo imprimir si algo falla (util para tarea programada / revision rapida).
if ($api -ne "OK" -or $web -ne "OK" -or $agtSt -ne "OK") {
  Write-Host "ALERTA: $linea" -ForegroundColor Yellow
} else {
  Write-Host "OK: $linea" -ForegroundColor Green
}
