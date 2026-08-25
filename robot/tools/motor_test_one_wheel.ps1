param(
    [string]$PortName = "COM5",
    [ValidateSet("left", "right")]
    [string]$Wheel = "left",
    [double]$SpeedMMPS = 80,
    [int]$DurationMs = 3000
)

$left = 0
$right = 0
if ($Wheel -eq "left") {
    $left = $SpeedMMPS
}
else {
    $right = $SpeedMMPS
}

$debugScript = Join-Path $PSScriptRoot "motor_serial_debug.ps1"
& $debugScript -PortName $PortName -LeftMMPS $left -RightMMPS $right -DurationMs $DurationMs -OpenRetries 10 -OpenRetryMs 500
