param(
    [int[]]$Ports = @(8000, 5173)
)

$ErrorActionPreference = "Continue"

foreach ($port in $Ports) {
    $lines = netstat -ano | findstr ":$port" | findstr "LISTENING"
    if (-not $lines) {
        Write-Host "No listener found on port $port"
        continue
    }

    foreach ($line in $lines) {
        $parts = ($line -split "\s+") | Where-Object { $_ }
        if ($parts.Length -lt 5) {
            continue
        }
        $processId = [int]$parts[-1]
        try {
            Stop-Process -Id $processId -Force -ErrorAction Stop
            Write-Host "Stopped PID $processId on port $port" -ForegroundColor Yellow
        } catch {
            Write-Host ("Unable to stop PID {0} on port {1}: {2}" -f $processId, $port, $_.Exception.Message)
        }
    }
}
