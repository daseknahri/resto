param(
    [string]$BackendPython = "",
    [string]$NpmCommand = "npm.cmd",
    [switch]$SkipBackendTests,
    [switch]$SkipFrontendLint,
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"

if (-not $BackendPython) {
    $BackendPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
}

if (-not (Test-Path $BackendPython)) {
    throw "Backend Python not found at '$BackendPython'."
}

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Action
    Write-Host "OK: $Label" -ForegroundColor Green
}

Write-Host "Release candidate freeze validation" -ForegroundColor Yellow
Write-Host "Repo root: $RepoRoot"

Push-Location $BackendDir
try {
    Invoke-Step "Backend system check" {
        & $BackendPython manage.py check
    }

    Invoke-Step "Migration drift check" {
        & $BackendPython manage.py makemigrations --check --dry-run
    }

    if (-not $SkipBackendTests) {
        Invoke-Step "Backend test suite" {
            & $BackendPython manage.py test tests -v 1
        }
    } else {
        Write-Host "Skipping backend tests" -ForegroundColor DarkYellow
    }
}
finally {
    Pop-Location
}

Push-Location $FrontendDir
try {
    if (-not $SkipFrontendLint) {
        Invoke-Step "Frontend lint" {
            & $NpmCommand run lint
        }
    } else {
        Write-Host "Skipping frontend lint" -ForegroundColor DarkYellow
    }

    if (-not $SkipFrontendBuild) {
        Invoke-Step "Frontend production build" {
            & $NpmCommand run build
        }
    } else {
        Write-Host "Skipping frontend build" -ForegroundColor DarkYellow
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Release candidate freeze validation completed successfully." -ForegroundColor Green
