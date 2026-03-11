param(
  [string]$BackendDir = "backend",
  [string]$OutputFile = "openapi.json"
)

$ErrorActionPreference = "Stop"

$backendPath = Resolve-Path $BackendDir
$outputPath = Join-Path $backendPath $OutputFile

Push-Location $backendPath
try {
  if (Test-Path ".\.venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
  } else {
    $py = "python"
  }

  & $py manage.py generateschema --format openapi-json --file $OutputFile
  Write-Host "OpenAPI schema exported to $outputPath"
}
finally {
  Pop-Location
}
