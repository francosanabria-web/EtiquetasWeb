# Registra tarea que corre monitoreo_salud.ps1 cada 5 min (solo lectura, sin cambios).
$ErrorActionPreference = "Stop"
$TaskName = "RedImpresionMonitoreo"
$Script = Join-Path $PSScriptRoot "monitoreo_salud.ps1"

$accion = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""

$disparador = New-ScheduledTaskTrigger -Once -At (Get-Date) `
  -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration ([TimeSpan]::MaxValue)

$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
  -LogonType Interactive -RunLevel Limited

$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable `
  -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)

Register-ScheduledTask -TaskName $TaskName -Action $accion -Trigger $disparador `
  -Principal $principal -Settings $ajustes -Force | Out-Null

Write-Host "Monitoreo pasivo instalado (cada 5 min). Log: scripts\logs\monitoreo.log" -ForegroundColor Green
