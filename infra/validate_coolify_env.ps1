param(
    [Parameter(Mandatory = $false)]
    [string]$EnvFile = ".\coolify.env.example",
    [switch]$ExpectProductionValues
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    Write-Error "Env file not found: $EnvFile"
    exit 1
}

$lines = Get-Content $EnvFile
$envMap = @{}
foreach ($raw in $lines) {
    $line = $raw.Trim()
    if (-not $line -or $line.StartsWith("#")) { continue }
    if ($line -notmatch "^[A-Z0-9_]+=.*$") {
        Write-Error "Invalid env format line: $line"
        exit 1
    }
    $parts = $line.Split("=", 2)
    $envMap[$parts[0]] = $parts[1]
}

$requiredKeys = @(
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    "DJANGO_CORS_ALLOWED_ORIGINS",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "DATABASE_URL",
    "REDIS_URL",
    "PUBLIC_MENU_BASE_URL",
    "TENANT_DOMAIN_SUFFIX",
    "DJANGO_MEDIA_STORAGE_BACKEND",
    "AWS_QUERYSTRING_EXPIRE",
    "DJANGO_PUBLIC_SCHEMA_HOSTS",
    "DJANGO_SESSION_COOKIE_SECURE",
    "DJANGO_CSRF_COOKIE_SECURE",
    "DJANGO_SESSION_COOKIE_DOMAIN",
    "DJANGO_CSRF_COOKIE_DOMAIN",
    "DJANGO_SESSION_COOKIE_SAMESITE",
    "DJANGO_CSRF_COOKIE_SAMESITE",
    "DJANGO_USE_X_FORWARDED_HOST",
    "DJANGO_SECURE_PROXY_SSL_HEADER",
    "DJANGO_DEFAULT_FROM_EMAIL",
    "DJANGO_SERVER_EMAIL",
    "DJANGO_EMAIL_BACKEND",
    "DJANGO_EMAIL_HOST",
    "DJANGO_EMAIL_PORT",
    "DJANGO_EMAIL_HOST_USER",
    "DJANGO_EMAIL_HOST_PASSWORD",
    "DJANGO_EMAIL_USE_TLS",
    "DJANGO_EMAIL_USE_SSL",
    "DJANGO_EMAIL_TIMEOUT",
    "DJANGO_EMAIL_FAIL_SILENTLY",
    "DJANGO_EMAIL_LOG_LEVEL",
    "DJANGO_SUPERADMIN_EMAIL",
    "DJANGO_SUPERADMIN_PASSWORD",
    "GUNICORN_WORKERS",
    "GUNICORN_TIMEOUT",
    "VITE_API_BASE_URL",
    "VITE_ADMIN_API_BASE_URL",
    "VITE_PLATFORM_PUBLIC_HOSTS",
    "VITE_APP_NAME"
)

$missing = @()
foreach ($key in $requiredKeys) {
    if (-not $envMap.ContainsKey($key)) {
        $missing += $key
    }
}

if ($missing.Count -gt 0) {
    Write-Host "Missing required keys:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
    exit 1
}

$warnings = @()

if ($envMap["DJANGO_DEBUG"] -ne "False") {
    $warnings += "DJANGO_DEBUG should be False in production."
}
if ($envMap["DJANGO_SESSION_COOKIE_SECURE"] -ne "True") {
    $warnings += "DJANGO_SESSION_COOKIE_SECURE should be True."
}
if ($envMap["DJANGO_CSRF_COOKIE_SECURE"] -ne "True") {
    $warnings += "DJANGO_CSRF_COOKIE_SECURE should be True."
}
if ($envMap["DJANGO_EMAIL_BACKEND"] -eq "django.core.mail.backends.console.EmailBackend") {
    $warnings += "Console email backend is not for production mail delivery."
}

$smtpBackend = [string]$envMap["DJANGO_EMAIL_BACKEND"]
if ($smtpBackend -eq "django.core.mail.backends.smtp.EmailBackend") {
    if (-not [string]$envMap["DJANGO_EMAIL_HOST"]) {
        Write-Host "DJANGO_EMAIL_HOST is required when using SMTP backend." -ForegroundColor Red
        exit 1
    }

    [int]$emailPort = 0
    if (-not [int]::TryParse([string]$envMap["DJANGO_EMAIL_PORT"], [ref]$emailPort) -or $emailPort -le 0) {
        Write-Host "DJANGO_EMAIL_PORT must be a positive integer when using SMTP backend." -ForegroundColor Red
        exit 1
    }

    $emailTls = ([string]$envMap["DJANGO_EMAIL_USE_TLS"]).Trim().ToLower()
    $emailSsl = ([string]$envMap["DJANGO_EMAIL_USE_SSL"]).Trim().ToLower()
    if (($emailTls -eq "true") -and ($emailSsl -eq "true")) {
        Write-Host "DJANGO_EMAIL_USE_TLS and DJANGO_EMAIL_USE_SSL cannot both be True." -ForegroundColor Red
        exit 1
    }

    if (($emailPort -eq 25) -and ($emailTls -ne "true") -and ($emailSsl -ne "true")) {
        $warnings += "SMTP is configured on port 25 without TLS/SSL; verify provider requirements."
    }

    if (-not ([string]$envMap["DJANGO_DEFAULT_FROM_EMAIL"]).Contains("@")) {
        Write-Host "DJANGO_DEFAULT_FROM_EMAIL must be a valid email address." -ForegroundColor Red
        exit 1
    }
    if (-not ([string]$envMap["DJANGO_SERVER_EMAIL"]).Contains("@")) {
        Write-Host "DJANGO_SERVER_EMAIL must be a valid email address." -ForegroundColor Red
        exit 1
    }
}

$tenantSuffix = [string]$envMap["TENANT_DOMAIN_SUFFIX"]
if (-not $tenantSuffix) {
    $warnings += "TENANT_DOMAIN_SUFFIX is not set. Provisioning will infer suffix from PUBLIC_MENU_BASE_URL."
}
elseif ($tenantSuffix.Contains("://")) {
    $warnings += "TENANT_DOMAIN_SUFFIX should be host only (no scheme), e.g. menu.yourdomain.com."
}

$viteApiBase = [string]$envMap["VITE_API_BASE_URL"]
$viteAdminApiBase = [string]$envMap["VITE_ADMIN_API_BASE_URL"]
if (($viteApiBase -ne "auto") -or ($viteAdminApiBase -ne "auto")) {
    $warnings += "VITE_API_BASE_URL and VITE_ADMIN_API_BASE_URL should stay 'auto' for the recommended same-host /api proxy deployment."
}

$mediaBackend = ([string]$envMap["DJANGO_MEDIA_STORAGE_BACKEND"]).Trim().ToLower()
if ($mediaBackend -notin @("local", "s3", "s3boto3", "object")) {
    $warnings += "DJANGO_MEDIA_STORAGE_BACKEND should be one of: local, s3."
}

$missingS3Keys = @()
if ($mediaBackend -in @("s3", "s3boto3", "object")) {
    foreach ($key in @("AWS_STORAGE_BUCKET_NAME", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")) {
        if (-not $envMap.ContainsKey($key) -or -not [string]$envMap[$key]) {
            $missingS3Keys += $key
        }
    }
    if ($missingS3Keys.Count -gt 0) {
        Write-Host "Missing required S3 keys for DJANGO_MEDIA_STORAGE_BACKEND=s3:" -ForegroundColor Red
        $missingS3Keys | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
        exit 1
    }

    [int]$queryExpire = 0
    if (-not [int]::TryParse([string]$envMap["AWS_QUERYSTRING_EXPIRE"], [ref]$queryExpire) -or $queryExpire -le 0) {
        Write-Host "Invalid AWS_QUERYSTRING_EXPIRE: must be a positive integer when DJANGO_MEDIA_STORAGE_BACKEND=s3." -ForegroundColor Red
        exit 1
    }
}

$placeholderKeys = @(
    "DJANGO_SECRET_KEY",
    "POSTGRES_PASSWORD",
    "DJANGO_SUPERADMIN_PASSWORD",
    "DATABASE_URL",
    "DJANGO_EMAIL_HOST_PASSWORD"
)
foreach ($key in $placeholderKeys) {
    $value = [string]$envMap[$key]
    if ($value.ToLower().Contains("replace_with")) {
        $warnings += "$key still uses placeholder text."
    }
}

if ($smtpBackend -eq "django.core.mail.backends.smtp.EmailBackend") {
    if (([string]$envMap["DJANGO_EMAIL_HOST"]).ToLower().Contains("yourprovider")) {
        $warnings += "DJANGO_EMAIL_HOST still uses placeholder text."
    }
    if (([string]$envMap["DJANGO_EMAIL_HOST_USER"]).ToLower().Contains("your_smtp_user")) {
        $warnings += "DJANGO_EMAIL_HOST_USER still uses placeholder text."
    }
}

if ($ExpectProductionValues) {
    if (-not ([string]$envMap["PUBLIC_MENU_BASE_URL"]).StartsWith("https://")) {
        $warnings += "PUBLIC_MENU_BASE_URL should use https:// in production."
    }
    if ([string]$envMap["DJANGO_ALLOWED_HOSTS"] -match "(^|,)(localhost|127\.0\.0\.1)(,|$)") {
        $warnings += "DJANGO_ALLOWED_HOSTS contains localhost/127.0.0.1 while ExpectProductionValues is enabled."
    }
    if ($smtpBackend -eq "django.core.mail.backends.console.EmailBackend") {
        $warnings += "Production should use SMTP backend instead of console backend."
    }
    if ([string]$envMap["DJANGO_EMAIL_FAIL_SILENTLY"] -ne "False") {
        $warnings += "DJANGO_EMAIL_FAIL_SILENTLY should be False in production so email failures are visible."
    }
}

Write-Host "Validation OK: required keys present in $EnvFile" -ForegroundColor Green
if ($warnings.Count -gt 0) {
    Write-Host "Warnings:" -ForegroundColor Yellow
    $warnings | ForEach-Object { Write-Host " - $_" -ForegroundColor Yellow }
}
else {
    Write-Host "No warnings." -ForegroundColor Green
}
