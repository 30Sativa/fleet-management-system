param(
    [string]$PortName = "COM5",
    [double]$SpeedMMPS = 80,
    [int]$DurationMs = 3000
)

$debugScript = Join-Path $PSScriptRoot "motor_serial_debug.ps1"
& $debugScript -PortName $PortName -LeftMMPS (-$SpeedMMPS) -RightMMPS (-$SpeedMMPS) -DurationMs $DurationMs -OpenRetries 10 -OpenRetryMs 500
