# ============================================================================
#  estado_panol.ps1
#  Estado de los servicios del portal (no impresion) + tarea PortalPanol.
# ============================================================================

$ErrorActionPreference = "SilentlyContinue"
$TaskName = "PortalPanol"
$Logs = Join-Path $PSScriptRoot "logs"

function Estado-Puerto([int]$port) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { "ARRIBA" } else { "CAIDO" }
}

function Estado-Health([string]$url, [bool]$accept503) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing -TimeoutSec 4 $url
    if ($r.StatusCode -eq 200) { return "ARRIBA" }
    if ($accept503 -and $r.StatusCode -eq 503) { return "CARGANDO" }
    return "CAIDO"
  } catch {
    $msg = "$_"
    if ($accept503 -and $msg -match "503") { return "CARGANDO" }
    return "CAIDO"
  }
}

Write-Host "==== Estado portal Pañol (sin impresion) ===="

$items = @(
  @{ Name = "KPIs (:8001)";         Url = "http://127.0.0.1:8001/health"; Accept503 = $true;  Port = 8001 }
  @{ Name = "Minuta (:8013)";       Url = "http://127.0.0.1:8013/health"; Accept503 = $false; Port = 8013 }
  @{ Name = "Solicitudes (:8014)";  Url = "http://127.0.0.1:8014/health"; Accept503 = $false; Port = 8014 }
  @{ Name = "Usuarios (:8015)";     Url = "http://127.0.0.1:8015/health"; Accept503 = $false; Port = 8015 }
  @{ Name = "Activos (:8016)";      Url = "http://127.0.0.1:8016/health"; Accept503 = $true;  Port = 8016 }
  @{ Name = "Reportes (:8017)";     Url = "http://127.0.0.1:8017/health"; Accept503 = $true;  Port = 8017 }
  @{ Name = "Salidas (:8018)";      Url = "http://127.0.0.1:8018/health"; Accept503 = $true;  Port = 8018 }
  @{ Name = "Email (:8020)";        Url = "http://127.0.0.1:8020/health"; Accept503 = $false; Port = 8020 }
)

foreach ($i in $items) {
  $h = Estado-Health $i.Url $i.Accept503
  if ($h -eq "CAIDO" -and (Estado-Puerto $i.Port) -eq "ARRIBA") { $h = "PUERTO OK / HEALTH NO" }
  Write-Host ("  {0,-24} {1}" -f $i.Name, $h)
}

Write-Host ("  {0,-24} {1}" -f "Portal (:5180)", (Estado-Puerto 5180))

$sup = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*supervisor_panol.ps1*" }
Write-Host ("  {0,-24} {1}" -f "Supervisor", $(if ($sup) { "ARRIBA (PID $($sup.ProcessId -join ','))" } else { "CAIDO" }))

$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Write-Host ("  {0,-24} {1}" -f "Tarea autostart", $(if ($t) { $t.State } else { "NO INSTALADA" }))

$marker = Join-Path $Logs "panol_reinicio_diario.marker"
if (Test-Path $marker) {
  $dia = (Get-Content $marker -Raw).Trim()
  Write-Host ("  {0,-24} {1}" -f "Reinicio diario", "hecho el $dia")
} else {
  Write-Host ("  {0,-24} {1}" -f "Reinicio diario", "pendiente (ventana 20:00-22:00)")
}

if (Test-Path (Join-Path $Logs "supervisor_panol.log")) {
  Write-Host "`n-- Ultimas lineas del supervisor --"
  Get-Content (Join-Path $Logs "supervisor_panol.log") -Tail 8
}
