# Usado por INICIAR_TODO.bat — espera health de KPIs / Minuta / Email / Solicitudes.
param(
    [int]$TimeoutSeg = 180,
    [int]$IntervaloSeg = 3
)

$checks = @(
    @{ Name = "KPIs";         Url = "http://127.0.0.1:8001/health" },
    @{ Name = "Minuta";       Url = "http://127.0.0.1:8013/health" },
    @{ Name = "Email";        Url = "http://127.0.0.1:8020/health" },
    @{ Name = "Solicitudes";  Url = "http://127.0.0.1:8014/health" }
)

$deadline = (Get-Date).AddSeconds($TimeoutSeg)
$pendientes = @($checks)

Write-Host "Esperando servicios backend (max ${TimeoutSeg}s)..."

while ($pendientes.Count -gt 0 -and (Get-Date) -lt $deadline) {
    $siguiente = @()
    foreach ($c in $pendientes) {
        try {
            $r = Invoke-WebRequest -Uri $c.Url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) {
                Write-Host "  [OK] $($c.Name)"
            } else {
                $siguiente += $c
            }
        } catch {
            $siguiente += $c
        }
    }
    $pendientes = $siguiente
    if ($pendientes.Count -gt 0) {
        Start-Sleep -Seconds $IntervaloSeg
    }
}

if ($pendientes.Count -gt 0) {
    Write-Host "  [AVISO] Sin respuesta: $($pendientes.Name -join ', ')"
    exit 1
}

# KPIs puede responder health mientras aún carga Excel — esperar estado ok
$kpisUrl = "http://127.0.0.1:8001/health"
Write-Host "Esperando que KPIs termine de cargar Excel..."
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod -Uri $kpisUrl -TimeoutSec 10
        if ($r.estado -eq "ok") {
            Write-Host "  [OK] KPIs datos listos."
            exit 0
        }
        if ($r.estado -eq "error") {
            Write-Host "  [AVISO] KPIs en error: $($r.detail)"
            exit 1
        }
        Write-Host "  ... cargando ($($r.mensaje))"
    } catch {
        Write-Host "  ... sin respuesta KPIs"
    }
    Start-Sleep -Seconds $IntervaloSeg
}

Write-Host "  [AVISO] KPIs no termino de cargar a tiempo."
exit 1
