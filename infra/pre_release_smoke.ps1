param(
    [string]$TenantHost = "demo.localhost",
    [string]$BackendScheme = "http",
    [string]$FrontendScheme = "http",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$AllowMenuLocked
)

$ErrorActionPreference = "Stop"

function Convert-JsonCompat {
    param(
        [Parameter(Mandatory = $true)][string]$InputText
    )

    $convertCmd = Get-Command ConvertFrom-Json -ErrorAction Stop
    if ($convertCmd.Parameters.ContainsKey("Depth")) {
        return ($InputText | ConvertFrom-Json -Depth 10)
    }
    return ($InputText | ConvertFrom-Json)
}

function Invoke-HttpCheck {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][int[]]$ExpectedStatus,
        [string]$Origin = "",
        [string]$RequireJsonField = "",
        [switch]$RequireCorsOrigin
    )

    $headers = @{}
    if ($Origin) {
        $headers["Origin"] = $Origin
    }

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url -Headers $headers -TimeoutSec 15
        $status = [int]$response.StatusCode

        if ($ExpectedStatus -notcontains $status) {
            return @{
                Passed = $false
                Message = "$Name failed. Status=$status, expected=$($ExpectedStatus -join ',')"
            }
        }

        if ($RequireCorsOrigin) {
            $corsHeader = $response.Headers["Access-Control-Allow-Origin"]
            if ([string]::IsNullOrWhiteSpace($corsHeader) -or $corsHeader -ne $Origin) {
                return @{
                    Passed = $false
                    Message = "$Name failed. CORS header '$corsHeader' does not match '$Origin'."
                }
            }
        }

        if ($RequireJsonField) {
            $json = $null
            try {
                $json = Convert-JsonCompat -InputText $response.Content
            } catch {
                return @{
                    Passed = $false
                    Message = "$Name failed. Response is not valid JSON."
                }
            }

            $segments = $RequireJsonField.Split(".")
            $value = $json
            foreach ($segment in $segments) {
                if ($null -eq $value) { break }
                if ($value.PSObject.Properties.Name -contains $segment) {
                    $value = $value.$segment
                } else {
                    $value = $null
                }
            }

            if ($null -eq $value) {
                return @{
                    Passed = $false
                    Message = "$Name failed. Missing JSON field '$RequireJsonField'."
                }
            }
        }

        return @{
            Passed = $true
            Message = "$Name passed (HTTP $status)"
        }
    } catch {
        $status = "N/A"
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        return @{
            Passed = $false
            Message = "$Name failed. Error=$($_.Exception.Message) Status=$status"
        }
    }
}

$backendPortPart = if ($BackendPort -gt 0) { ":$BackendPort" } else { "" }
$frontendPortPart = if ($FrontendPort -gt 0) { ":$FrontendPort" } else { "" }
$backendBase = "${BackendScheme}://$TenantHost$backendPortPart"
$frontendBase = "${FrontendScheme}://$TenantHost$frontendPortPart"
$menuStatuses = @(200)
if ($AllowMenuLocked) {
    $menuStatuses = @(200, 403, 503)
}

Write-Host "Running pre-release smoke checks for tenant '$TenantHost'..." -ForegroundColor Cyan
Write-Host "Backend: $backendBase"
Write-Host "Frontend: $frontendBase"

$checks = @(
    @{ Name = "Frontend home"; Url = "$frontendBase/"; Expected = @(200) },
    @{ Name = "Backend health"; Url = "$backendBase/api/health/"; Expected = @(200); Json = "status"; Origin = $frontendBase; Cors = $true },
    @{ Name = "Tenant meta"; Url = "$backendBase/api/meta/"; Expected = @(200); Json = "profile" ; Origin = $frontendBase; Cors = $true },
    @{ Name = "Session endpoint"; Url = "$backendBase/api/session/"; Expected = @(200); Json = "authenticated"; Origin = $frontendBase; Cors = $true },
    @{ Name = "Categories endpoint"; Url = "$backendBase/api/categories/"; Expected = $menuStatuses; Origin = $frontendBase; Cors = $true }
)

$failed = @()
foreach ($check in $checks) {
    $result = Invoke-HttpCheck `
        -Name $check.Name `
        -Url $check.Url `
        -ExpectedStatus $check.Expected `
        -Origin ($check.Origin) `
        -RequireJsonField ($check.Json) `
        -RequireCorsOrigin:([bool]$check.Cors)

    if ($result.Passed) {
        Write-Host "[PASS] $($result.Message)" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] $($result.Message)" -ForegroundColor Red
        $failed += $result
    }
}

if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "Smoke checks failed: $($failed.Count)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All smoke checks passed." -ForegroundColor Green
exit 0
