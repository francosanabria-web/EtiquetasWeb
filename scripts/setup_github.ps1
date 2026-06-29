# ============================================================================
#  setup_github.ps1 — Conectar AppWebSalidas a un repo nuevo en GitHub
#
#  Uso (después de crear el repo vacío en github.com):
#    powershell -ExecutionPolicy Bypass -File scripts\setup_github.ps1 `
#      -RepoUrl "https://github.com/TU_USUARIO/AppWebSalidas.git"
# ============================================================================

param(
  [Parameter(Mandatory = $true)]
  [string]$RepoUrl
)

$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $PSScriptRoot
Set-Location $Raiz

if (git remote get-url origin 2>$null) {
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
