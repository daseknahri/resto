param(
    [Parameter(Mandatory = $true)][string]$TenantSlug,
    [string]$BaseDomain = "menu.kepoli.com",
    [string]$PublicHost = "menu.kepoli.com",
    [string]$AdminHost = "admin.menu.kepoli.com",
    [string]$TableSlug = "table-1",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TenantHost = "$TenantSlug.$BaseDomain"

function Invoke-HealthCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$Url
    )

    Write-Host "Checking $Label -> $Url" -ForegroundColor Cyan
    $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url -TimeoutSec 20
    if ([int]$response.StatusCode -ne 200) {
        throw "$Label failed with HTTP $($response.StatusCode)"
    }
    Write-Host "OK: $Label" -ForegroundColor Green
}

Write-Host "Production tenant smoke wrapper" -ForegroundColor Yellow
Write-Host "Public host: $PublicHost"
Write-Host "Admin host: $AdminHost"
Write-Host "Tenant host: $TenantHost"
Write-Host "Table slug: $TableSlug"

if ($DryRun) {
    Write-Host ""
    Write-Host "Dry run only. Commands that would be executed:" -ForegroundColor DarkYellow
    Write-Host "1. GET https://$PublicHost/health"
    Write-Host "2. GET https://$AdminHost/health"
    Write-Host "3. GET https://$PublicHost/api/session/"
    Write-Host "4. GET https://$TenantHost/api/health/"
    Write-Host "5. powershell -ExecutionPolicy Bypass -File .\infra\pre_release_smoke.ps1 -TenantHost $TenantHost -BackendScheme https -FrontendScheme https -BackendPort 443 -FrontendPort 443"
    Write-Host "6. powershell -ExecutionPolicy Bypass -File .\infra\customer_flow_smoke.ps1 -FrontendBaseUrl https://$TenantHost -ApiBaseUrl https://$TenantHost/api -TableSlug $TableSlug"
    exit 0
}

Invoke-HealthCheck -Label "Public health" -Url "https://$PublicHost/health"
Invoke-HealthCheck -Label "Admin health" -Url "https://$AdminHost/health"
Invoke-HealthCheck -Label "Public session endpoint" -Url "https://$PublicHost/api/session/"
Invoke-HealthCheck -Label "Tenant API health" -Url "https://$TenantHost/api/health/"

Write-Host ""
Write-Host "Running tenant pre-release smoke..." -ForegroundColor Yellow
& powershell -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "pre_release_smoke.ps1") `
    -TenantHost $TenantHost `
    -BackendScheme https `
    -FrontendScheme https `
    -BackendPort 443 `
    -FrontendPort 443

Write-Host ""
Write-Host "Running customer-flow smoke..." -ForegroundColor Yellow
& powershell -ExecutionPolicy Bypass -File (Join-Path $ScriptDir "customer_flow_smoke.ps1") `
    -FrontendBaseUrl "https://$TenantHost" `
    -ApiBaseUrl "https://$TenantHost/api" `
    -TableSlug $TableSlug

Write-Host ""
Write-Host "Production tenant smoke completed successfully for $TenantHost" -ForegroundColor Green
