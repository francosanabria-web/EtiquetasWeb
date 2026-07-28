# Supervisor minutas-api + minutas-web (LAN)
$ErrorActionPreference = "SilentlyContinue"
$Raiz = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Raiz "services\minutas-api"
$WebDir = Join-Path $Raiz "services\minutas-web"
$Logs = Join-Path $PSScriptRoot "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

$Py = Join-Path $ApiDir ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    $Py = Join-Path (Join-Path $Raiz "services\etiquetas-api") ".venv\Scripts\python.exe"
}
$ViteJs = Join-Path $WebDir "node_modules\vite\bin\vite.js"
$ApiPort = 8012
$WebPort = 5175
$IntervaloSeg = 25

function Test-Puerto {
    param([int]$port)
    $c = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $c
}

function Test-ApiViva {
    try {
        $uri = "http://127.0.0.1:$ApiPort/health"
        $r = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 4
        return $r.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Stop-ApiColgada {
    if (-not (Test-Puerto -port $ApiPort)) { return }
    if (Test-ApiViva) { return }
    Write-Host "API en puerto $ApiPort no responde - reiniciando proceso..."
    Get-NetTCPConnection -LocalPort $ApiPort -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

function Start-Api {
    if (Test-Puerto -port $ApiPort) { return }
    if (-not (Test-Path $Py)) {
        Write-Host "No se encontro Python en: $Py"
        return
    }
    $outLog = Join-Path $Logs "minutas-api.log"
    $errLog = Join-Path $Logs "minutas-api.err"
    Start-Process -WindowStyle Hidden -FilePath $Py `
        -ArgumentList "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", $ApiPort `
        -WorkingDirectory $ApiDir `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog
}

function Start-Web {
    if (Test-Puerto -port $WebPort) { return }
    if (-not (Test-Path $ViteJs)) {
        Write-Host "No se encontro Vite. Ejecute npm install en minutas-web."
        return
    }
    $outLog = Join-Path $Logs "minutas-web.log"
    $errLog = Join-Path $Logs "minutas-web.err"
    Start-Process -WindowStyle Hidden -FilePath "node" `
        -ArgumentList $ViteJs, "--host", "0.0.0.0", "--port", $WebPort `
        -WorkingDirectory $WebDir `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog
}

Write-Host "Supervisor Minutas - API :$ApiPort Web :$WebPort (Ctrl+C para salir)"
while ($true) {
    Stop-ApiColgada
    Start-Api
    Start-Web
    Start-Sleep -Seconds $IntervaloSeg
}
