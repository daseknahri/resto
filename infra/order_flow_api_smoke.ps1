param(
    [string]$TenantHost = "demo.localhost",
    [int]$ApiPort = 8000
)

$ErrorActionPreference = "Stop"

function Invoke-JsonRequest {
    param(
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Url,
        [object]$Body = $null
    )

    $jsonBody = $null
    if ($null -ne $Body) {
        $jsonBody = $Body | ConvertTo-Json -Depth 8
    }

    try {
        if ($Method -eq "GET") {
            $data = Invoke-RestMethod -Uri $Url -Method Get
        } else {
            $data = Invoke-RestMethod -Uri $Url -Method Post -ContentType "application/json" -Body $jsonBody
        }
        return @{
            StatusCode = 200
            Data = $data
            Error = $null
        }
    } catch {
        $statusCode = -1
        $errorPayload = $null
        if ($_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
            } catch {}
            try {
                $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
                $raw = $reader.ReadToEnd()
                if ($raw) {
                    $errorPayload = $raw | ConvertFrom-Json
                }
            } catch {}
        }
        return @{
            StatusCode = $statusCode
            Data = $null
            Error = $errorPayload
        }
    }
}

$apiBase = "http://$TenantHost`:$ApiPort/api"

Write-Host "Order-flow API smoke test started for $apiBase" -ForegroundColor Cyan

$health = Invoke-JsonRequest -Method GET -Url "$apiBase/health/"
if ($health.StatusCode -ne 200) {
    throw "Health check failed on $apiBase/health/. Ensure backend is running."
}

$categories = Invoke-JsonRequest -Method GET -Url "$apiBase/categories/"
if ($categories.StatusCode -ne 200 -or -not $categories.Data -or $categories.Data.Count -eq 0) {
    throw "No categories found; seed demo data first."
}

$categorySlug = $categories.Data[0].slug
$dishes = Invoke-JsonRequest -Method GET -Url "$apiBase/dishes/?category=$categorySlug"
if ($dishes.StatusCode -ne 200 -or -not $dishes.Data -or $dishes.Data.Count -eq 0) {
    throw "No dishes found for category '$categorySlug'."
}

$dishSlug = $dishes.Data[0].slug
Write-Host "Using category '$categorySlug' and dish '$dishSlug'" -ForegroundColor DarkCyan

$results = @()

function Add-Result {
    param(
        [string]$Name,
        [bool]$Pass,
        [string]$Detail
    )
    $results += [PSCustomObject]@{
        test = $Name
        pass = $Pass
        detail = $Detail
    }
}

# Case 1: General menu order without required info must fail (400)
$missingGeneral = Invoke-JsonRequest -Method POST -Url "$apiBase/order-handoff/" -Body @{
    items = @(@{ slug = $dishSlug; qty = 1 })
}
Add-Result -Name "general_missing_required" -Pass ($missingGeneral.StatusCode -eq 400) -Detail ("status={0}" -f $missingGeneral.StatusCode)

# Case 2: General pickup order must succeed (200)
$generalPickup = Invoke-JsonRequest -Method POST -Url "$apiBase/order-handoff/" -Body @{
    fulfillment_type = "pickup"
    customer_name = "QA Pickup"
    customer_phone = "+212600000111"
    customer_note = "Smoke pickup"
    items = @(@{ slug = $dishSlug; qty = 1 })
}
$pickupHasFulfillment = $false
if ($generalPickup.StatusCode -eq 200 -and $generalPickup.Data -and $generalPickup.Data.message) {
    $pickupHasFulfillment = [string]$generalPickup.Data.message -match "Fulfillment:\s+Pickup"
}
Add-Result -Name "general_pickup_success" -Pass ($generalPickup.StatusCode -eq 200 -and $pickupHasFulfillment) -Detail ("status={0}" -f $generalPickup.StatusCode)

# Case 3: Table-context minimal flow must succeed (200) with no customer required
$tableMinimal = Invoke-JsonRequest -Method POST -Url "$apiBase/order-handoff/" -Body @{
    table_label = "Table QA-9"
    customer_note = "Smoke table"
    items = @(@{ slug = $dishSlug; qty = 1 })
}
$tableHasContext = $false
if ($tableMinimal.StatusCode -eq 200 -and $tableMinimal.Data -and $tableMinimal.Data.message) {
    $tableHasContext = [string]$tableMinimal.Data.message -match "Table:\s+Table QA-9"
}
Add-Result -Name "table_minimal_success" -Pass ($tableMinimal.StatusCode -eq 200 -and $tableHasContext) -Detail ("status={0}" -f $tableMinimal.StatusCode)

# Case 4: Delivery without location should fail (400)
$deliveryMissingLocation = Invoke-JsonRequest -Method POST -Url "$apiBase/order-handoff/" -Body @{
    fulfillment_type = "delivery"
    customer_name = "QA Delivery"
    customer_phone = "+212600000222"
    delivery_address = "Main street"
    items = @(@{ slug = $dishSlug; qty = 1 })
}
Add-Result -Name "delivery_requires_location" -Pass ($deliveryMissingLocation.StatusCode -eq 400) -Detail ("status={0}" -f $deliveryMissingLocation.StatusCode)

# Case 5: Delivery with map URL should succeed (200)
$deliveryWithMap = Invoke-JsonRequest -Method POST -Url "$apiBase/order-handoff/" -Body @{
    fulfillment_type = "delivery"
    customer_name = "QA Delivery"
    customer_phone = "+212600000333"
    delivery_address = "Main street"
    delivery_location_url = "https://maps.google.com/?q=33.5731,-7.5898"
    items = @(@{ slug = $dishSlug; qty = 1 })
}
$deliveryHasMapLine = $false
if ($deliveryWithMap.StatusCode -eq 200 -and $deliveryWithMap.Data -and $deliveryWithMap.Data.message) {
    $deliveryHasMapLine = [string]$deliveryWithMap.Data.message -match "Map:"
}
Add-Result -Name "delivery_with_map_success" -Pass ($deliveryWithMap.StatusCode -eq 200 -and $deliveryHasMapLine) -Detail ("status={0}" -f $deliveryWithMap.StatusCode)

# Case 6: Checkout intent in Basic is expected 403 (or 202 in checkout-enabled plan)
$checkout = Invoke-JsonRequest -Method POST -Url "$apiBase/checkout-intent/" -Body @{
    fulfillment_type = "pickup"
    customer_name = "QA Checkout"
    customer_phone = "+212600000444"
    items = @(@{ slug = $dishSlug; qty = 1 })
}
$checkoutPass = ($checkout.StatusCode -eq 403 -or $checkout.StatusCode -eq 202)
Add-Result -Name "checkout_plan_gate" -Pass $checkoutPass -Detail ("status={0}" -f $checkout.StatusCode)

Write-Host ""
Write-Host "Smoke results:" -ForegroundColor Cyan
$results | Format-Table -AutoSize

$failed = @($results | Where-Object { -not $_.pass })
if ($failed.Count -gt 0) {
    Write-Host ""
    Write-Host "FAILED: $($failed.Count) checks did not pass." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "All order-flow checks passed." -ForegroundColor Green
