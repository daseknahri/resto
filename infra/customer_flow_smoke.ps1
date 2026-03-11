param(
    [string]$TenantHost = "demo.localhost",
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173,
    [string]$TableSlug = "table-1",
    [string]$FrontendBaseUrl = "",
    [string]$ApiBaseUrl = ""
)

$ErrorActionPreference = "Stop"

function Convert-JsonCompat {
    param(
        [Parameter(Mandatory = $true)][string]$InputText
    )

    $convertCmd = Get-Command ConvertFrom-Json -ErrorAction Stop
    if ($convertCmd.Parameters.ContainsKey("Depth")) {
        return ($InputText | ConvertFrom-Json -Depth 12)
    }
    return ($InputText | ConvertFrom-Json)
}

function Read-ResponseBody {
    param($Response)

    if ($null -eq $Response) { return "" }

    try {
        $stream = $Response.GetResponseStream()
        if ($null -eq $stream) { return "" }
        $reader = New-Object System.IO.StreamReader($stream)
        return $reader.ReadToEnd()
    } catch {
        return ""
    }
}

function Invoke-HttpJson {
    param(
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Url,
        [object]$Body = $null,
        [string]$Origin = ""
    )

    $headers = @{}
    if ($Origin) {
        $headers["Origin"] = $Origin
    }

    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = $Body | ConvertTo-Json -Depth 12
    }

    try {
        if ($Method -eq "GET") {
            $response = Invoke-WebRequest -UseBasicParsing -Method Get -Uri $Url -Headers $headers -TimeoutSec 20
        } else {
            $response = Invoke-WebRequest -UseBasicParsing -Method Post -Uri $Url -Headers $headers -ContentType "application/json" -Body $jsonBody -TimeoutSec 20
        }

        $json = $null
        try {
            $json = Convert-JsonCompat -InputText $response.Content
        } catch {}

        return @{
            StatusCode = [int]$response.StatusCode
            Content = $response.Content
            Json = $json
            Headers = $response.Headers
        }
    } catch {
        $status = -1
        $content = ""
        if ($_.Exception.Response) {
            try { $status = [int]$_.Exception.Response.StatusCode } catch {}
            $content = Read-ResponseBody -Response $_.Exception.Response
        }
        $json = $null
        if ($content) {
            try {
                $json = Convert-JsonCompat -InputText $content
            } catch {}
        }
        return @{
            StatusCode = $status
            Content = $content
            Json = $json
            Headers = @{}
        }
    }
}

function Normalize-BaseUrl {
    param(
        [Parameter(Mandatory = $true)][string]$Value
    )

    return ($Value.Trim().TrimEnd("/"))
}

if ($FrontendBaseUrl) {
    $frontendBase = Normalize-BaseUrl -Value $FrontendBaseUrl
} else {
    $frontendBase = "http://$TenantHost`:$WebPort"
}

if ($ApiBaseUrl) {
    $apiBase = Normalize-BaseUrl -Value $ApiBaseUrl
} else {
    try {
        $uri = [System.Uri]$frontendBase
        $defaultPort = if ($uri.Scheme -eq "https") { 443 } else { 80 }
        if ($uri.Port -eq $defaultPort) {
            $apiBase = "$($uri.Scheme)://$($uri.Host)/api"
        } else {
            $apiBase = "$($uri.Scheme)://$($uri.Host):$($uri.Port)/api"
        }
    } catch {
        $apiBase = "http://$TenantHost`:$ApiPort/api"
    }
}

Write-Host "Customer-flow smoke started" -ForegroundColor Cyan
Write-Host "Frontend: $frontendBase"
Write-Host "API: $apiBase"
Write-Host "Table slug: $TableSlug"

$results = @()

function Add-Result {
    param(
        [string]$Test,
        [bool]$Pass,
        [string]$Detail
    )

    $script:results += [PSCustomObject]@{
        test = $Test
        pass = $Pass
        detail = $Detail
    }
}

$routes = @(
    "/menu",
    "/browse",
    "/cart",
    "/reserve",
    "/t/$TableSlug"
)

foreach ($path in $routes) {
    $url = "$frontendBase$path"
    $resp = Invoke-HttpJson -Method GET -Url $url
    Add-Result -Test "route_$path" -Pass ($resp.StatusCode -eq 200) -Detail ("status={0}" -f $resp.StatusCode)
}

$tableContext = Invoke-HttpJson -Method GET -Url "$apiBase/table-context/$([uri]::EscapeDataString($TableSlug))/" -Origin $frontendBase
$tableContextPass = $tableContext.StatusCode -eq 200 -and $tableContext.Json -and $tableContext.Json.slug
Add-Result -Test "table_context_api" -Pass $tableContextPass -Detail ("status={0}" -f $tableContext.StatusCode)

$categories = Invoke-HttpJson -Method GET -Url "$apiBase/categories/" -Origin $frontendBase
$categoriesPass = $categories.StatusCode -eq 200 -and $categories.Json -and $categories.Json.Count -gt 0
Add-Result -Test "categories_available" -Pass $categoriesPass -Detail ("status={0}" -f $categories.StatusCode)

$dishSlug = ""
if ($categoriesPass) {
    $dishesPass = $false
    $lastDishStatus = 200

    foreach ($category in $categories.Json) {
        $categorySlug = [string]$category.slug
        if (-not $categorySlug) { continue }

        $dishes = Invoke-HttpJson -Method GET -Url "$apiBase/dishes/?category=$([uri]::EscapeDataString($categorySlug))" -Origin $frontendBase
        $lastDishStatus = $dishes.StatusCode
        if ($dishes.StatusCode -eq 200 -and $dishes.Json -and $dishes.Json.Count -gt 0) {
            $dishSlug = [string]$dishes.Json[0].slug
            $dishesPass = $true
            break
        }
    }

    if (-not $dishesPass) {
        $allDishes = Invoke-HttpJson -Method GET -Url "$apiBase/dishes/" -Origin $frontendBase
        $lastDishStatus = $allDishes.StatusCode
        if ($allDishes.StatusCode -eq 200 -and $allDishes.Json -and $allDishes.Json.Count -gt 0) {
            $dishSlug = [string]$allDishes.Json[0].slug
            $dishesPass = $true
        }
    }

    Add-Result -Test "dishes_available" -Pass $dishesPass -Detail ("status={0}" -f $lastDishStatus)
} else {
    Add-Result -Test "dishes_available" -Pass $false -Detail "skipped: categories missing"
}

if ($tableContextPass -and $dishSlug) {
    $handoff = Invoke-HttpJson -Method POST -Url "$apiBase/order-handoff/" -Body @{
        table_slug = $TableSlug
        items = @(
            @{
                slug = $dishSlug
                qty = 1
            }
        )
    } -Origin $frontendBase

    $carryoverPass = $handoff.StatusCode -eq 200 -and $handoff.Json -and ([string]$handoff.Json.table_slug).ToLower() -eq $TableSlug.ToLower()
    Add-Result -Test "table_context_carryover_order_handoff" -Pass $carryoverPass -Detail ("status={0}" -f $handoff.StatusCode)
} else {
    Add-Result -Test "table_context_carryover_order_handoff" -Pass $false -Detail "skipped: missing table context or dish seed data"
}

Write-Host ""
Write-Host "Results:" -ForegroundColor Cyan
$results | Format-Table -AutoSize

$failed = @($results | Where-Object { -not $_.pass })
if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "FAILED: $($failed.Count) customer-flow checks did not pass." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All customer-flow checks passed." -ForegroundColor Green
exit 0
