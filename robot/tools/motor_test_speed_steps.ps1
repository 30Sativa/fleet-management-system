param(
    [string]$PortName = "COM5",
    [double[]]$SpeedsMMPS = @(20, 50, 100, 150, 100, 50, 20),
    [int]$StepDurationMs = 1500,
    [int]$PauseMs = 300
)

$debugScript = Join-Path $PSScriptRoot "motor_serial_debug.ps1"
foreach ($speed in $SpeedsMMPS) {
    Write-Host ("=== Speed {0} mm/s for {1} ms ===" -f $speed, $StepDurationMs)
    & $debugScript -PortName $PortName -LeftMMPS $speed -RightMMPS $speed -DurationMs $StepDurationMs -OpenRetries 10 -OpenRetryMs 500
    Start-Sleep -Milliseconds $PauseMs
}
