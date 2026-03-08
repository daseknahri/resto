param(
  [string[]]$TenantSlugs = @("demo"),
  [string]$DomainSuffix = "localhost",
  [switch]$Apply
)

$ErrorActionPreference = "Stop"
$hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
$normalizedSuffix = $DomainSuffix.Trim().TrimStart(".").ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($normalizedSuffix)) {
  throw "DomainSuffix cannot be empty."
}

$requiredHosts = @()
foreach ($slugValue in $TenantSlugs) {
  $raw = ""
  if ($null -ne $slugValue) { $raw = [string]$slugValue }
  foreach ($token in $raw.Split(",")) {
    $cleanSlug = $token.Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($cleanSlug)) { continue }
    $requiredHosts += "$cleanSlug.$normalizedSuffix"
  }
}

if (-not $requiredHosts.Count) {
  throw "Provide at least one tenant slug. Example: -TenantSlugs demo,dede"
}

$lines = Get-Content -Path $hostsPath -ErrorAction Stop
$missing = @()
foreach ($tenantHost in $requiredHosts) {
  $pattern = "^\s*127\.0\.0\.1\s+$([regex]::Escape($tenantHost))(\s|$)"
  $exists = $lines | Where-Object { $_ -match $pattern }
  if (-not $exists) {
    $missing += $tenantHost
  }
}

Write-Host "Hosts file:" $hostsPath
Write-Host "Checked tenant hosts:" ($requiredHosts -join ", ")

if (-not $missing.Count) {
  Write-Host "All required host mappings already exist." -ForegroundColor Green
} else {
  Write-Host "Missing host mappings:" ($missing -join ", ") -ForegroundColor Yellow
  if ($Apply) {
    try {
      Add-Content -Path $hostsPath -Value ""
      Add-Content -Path $hostsPath -Value "# resto-local-tenants"
      foreach ($tenantHost in $missing) {
        Add-Content -Path $hostsPath -Value "127.0.0.1 $tenantHost"
      }
      Write-Host "Added missing host mappings." -ForegroundColor Green
    } catch {
      Write-Host "Failed to update hosts file. Run PowerShell as Administrator and retry with -Apply." -ForegroundColor Red
      throw
    }
  } else {
    Write-Host "Dry-run mode. Re-run with -Apply (as Administrator) to add missing entries." -ForegroundColor Yellow
  }
}

Write-Host ""
Write-Host "Test URLs:"
foreach ($tenantHost in $requiredHosts) {
  Write-Host "  Frontend: http://$tenantHost`:5173/"
  Write-Host "  API Meta:  http://$tenantHost`:8000/api/meta/"
  Write-Host "  Health:    http://$tenantHost`:8000/api/health/"
}
