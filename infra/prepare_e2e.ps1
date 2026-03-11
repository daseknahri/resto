param(
    [string]$AdminEmail = "e2e-admin@example.com",
    [string]$AdminPassword = "E2E_Admin_123!",
    [string]$DemoDomain = "demo.localhost",
    [string]$OwnerEmail = "test_resto_user@demo.local",
    [string]$OwnerPassword = "admin123"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendDir = Join-Path $repoRoot "backend"

$pythonCandidates = @(
    (Join-Path $backendDir ".venv\Scripts\python.exe"),
    (Join-Path $backendDir ".venv\Scripts\python"),
    "python"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
    if ($candidate -eq "python") {
        $python = $candidate
        break
    }
    if (Test-Path $candidate) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    throw "Python executable not found. Ensure backend virtualenv exists."
}

Push-Location $backendDir
try {
    function Invoke-Manage {
        param([string[]]$CommandArgs)
        if (-not $CommandArgs -or $CommandArgs.Count -eq 0) {
            throw "Invoke-Manage requires at least one command argument."
        }
        & $python manage.py @CommandArgs
        if ($LASTEXITCODE -ne 0) {
            throw "manage.py $($CommandArgs -join ' ') failed with exit code $LASTEXITCODE"
        }
    }

    Invoke-Manage -CommandArgs @("migrate")
    Invoke-Manage -CommandArgs @("shell", "-c", "from django.core.cache import cache; cache.clear(); print('Cache cleared')")
    Invoke-Manage -CommandArgs @("seed_plans", "--with-demo", "--domain", $DemoDomain, "--email", $AdminEmail, "--password", $AdminPassword)
    Invoke-Manage -CommandArgs @("ensure_platform_admin", "--email", $AdminEmail, "--password", $AdminPassword)
    Invoke-Manage -CommandArgs @(
        "shell",
        "-c",
        "from accounts.models import User; from tenancy.models import Tenant; t = Tenant.objects.get(slug='demo'); u, _ = User.objects.get_or_create(email='$OwnerEmail', defaults={'username': '$OwnerEmail', 'role': 'tenant_owner', 'tenant': t}); u.username = '$OwnerEmail'; u.role = 'tenant_owner'; u.tenant = t; u.is_active = True; u.set_password('$OwnerPassword'); u.save(); print('Demo owner ensured:', u.email)"
    )
    Write-Host "E2E preparation complete." -ForegroundColor Green
    Write-Host "Admin credentials: $AdminEmail / $AdminPassword"
    Write-Host "Owner credentials: $OwnerEmail / $OwnerPassword"
} finally {
    Pop-Location
}
