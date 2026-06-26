# ============================================================================
#  instalar_autostart.ps1
#  Registra una TAREA PROGRAMADA que lanza el supervisor al iniciar sesion,
#  oculto y reiniciandose solo si falla. Ejecutar UNA sola vez (doble click o
#  desde PowerShell). NO requiere administrador (corre en tu propia sesion).
#
#  La tarea corre "solo cuando el usuario esta logueado" a proposito: asi el
#  agente tiene acceso a la impresora predeterminada de tu sesion.
# ============================================================================

$ErrorActionPreference = "Stop"

$TaskName = "RedImpresionPanol"
$Supervisor = Join-Path $PSScriptRoot "supervisor_impresion.ps1"

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

# Arrancar ya mismo, sin esperar al proximo inicio de sesion.
Start-ScheduledTask -TaskName $TaskName
Write-Host "Supervisor iniciado. En ~30s deberian estar arriba la API, el agente y la web." -ForegroundColor Green
Write-Host "Para ver el estado:  powershell -ExecutionPolicy Bypass -File `"$PSScriptRoot\estado_impresion.ps1`""
