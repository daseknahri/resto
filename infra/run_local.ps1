param(
    [string]$TenantHost = "demo.localhost",
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"

$backendPython = Join-Path $backendDir ".venv\\Scripts\\python.exe"
if (-not (Test-Path $backendPython)) {
    throw "Backend venv python not found at $backendPython"
}

$backendCmd = "Set-Location '$backendDir'; & '$backendPython' manage.py runserver 0.0.0.0:$ApiPort --noreload"
$frontendCmd = "Set-Location '$frontendDir'; npm.cmd run dev -- --host --port $WebPort"

Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $backendCmd) | Out-Null
Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $frontendCmd) | Out-Null

Write-Host "Started local app windows." -ForegroundColor Green
Write-Host "Customer menu: http://$TenantHost`:$WebPort/menu"
Write-Host "Owner workspace: http://$TenantHost`:$WebPort/owner"
Write-Host "Admin console: http://$TenantHost`:$WebPort/admin-console"
Write-Host "API health: http://$TenantHost`:$ApiPort/api/health/"
