# ============================================================================
#  setup_github.ps1 — Conectar AppWebSalidas a un repo nuevo en GitHub
#
#  Uso (después de crear el repo vacío en github.com):
#    powershell -ExecutionPolicy Bypass -File "C:\Users\Mantenimiento\Desktop\AppWebSalidas\scripts\setup_github.ps1" -RepoUrl "https://github.com/TU_USUARIO/TU_REPO.git"
#
#  IMPORTANTE: usar -File y la ruta completa; no ejecutar el .ps1 solo con Enter.
# ============================================================================

param(
  [Parameter(Mandatory = $true)]
  [string]$RepoUrl
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

# Quitar comillas si el usuario las pegó dentro del valor.
$RepoUrl = $RepoUrl.Trim().Trim('"').Trim("'")

$remoteActual = git remote 2>$null | Select-String -Pattern "^origin$" -Quiet
if ($remoteActual) {
  Write-Host "Remote 'origin' ya existe:" (git remote get-url origin)
  $r = Read-Host "¿Reemplazar? (s/N)"
  if ($r -ne "s") { exit 0 }
  git remote remove origin
}

git remote add origin $RepoUrl
git branch -M main
Write-Host "Remote configurado. Empujando rama main..."
git push -u origin main
Write-Host "Listo. Repo en: $RepoUrl" -ForegroundColor Green
