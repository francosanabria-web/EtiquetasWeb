# ============================================================================
#  instalar_autostart_panol.ps1
#  Registra la tarea "PortalPanol" que lanza supervisor_panol.ps1 al iniciar
#  sesion (oculto). NO toca RedImpresionPanol / etiquetas.
#  Ejecutar UNA vez. No requiere administrador.
# ============================================================================

$ErrorActionPreference = "Stop"

$TaskName = "PortalPanol"
$Supervisor = Join-Path $PSScriptRoot "supervisor_panol.ps1"

if (-not (Test-Path $Supervisor)) {
  Write-Host "No se encontro el supervisor en: $Supervisor" -ForegroundColor Red
  exit 1
}

$accion = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Supervisor`""

$disparador = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
  -LogonType Interactive -RunLevel Limited

$ajustes = New-ScheduledTaskSettingsSet `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -MultipleInstances IgnoreNew `
  -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
  -ExecutionTimeLimit ([TimeSpan]::Zero)
$ajustes.Hidden = $true

Register-ScheduledTask -TaskName $TaskName -Action $accion -Trigger $disparador `
  -Principal $principal -Settings $ajustes -Force | Out-Null

Write-Host "Tarea '$TaskName' registrada (se inicia sola al iniciar sesion)." -ForegroundColor Green

Start-ScheduledTask -TaskName $TaskName
Write-Host "Supervisor portal iniciado. En ~30-60s deberian responder los backends y :5180." -ForegroundColor Green
Write-Host "Estado:  powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\estado_panol.ps1`""
Write-Host "Frenar:  powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\detener_panol.ps1`""
Write-Host ""
Write-Host "AVISO: no uses INICIAR_TODO.bat mientras esta tarea este activa (mismos puertos)." -ForegroundColor Yellow
