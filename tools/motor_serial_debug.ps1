param(
    [string]$PortName = "COM5",
    [int]$BaudRate = 115200,
    [double]$LeftMMPS = 2.0,
    [double]$RightMMPS = 2.0,
    [int]$DurationMs = 5000,
    [int]$PeriodMs = 20,
    [int]$SummaryMs = 500,
    [int]$StartSeq = 1,
    [switch]$VerboseLog,
    [switch]$NoStop
)

$ErrorActionPreference = "Stop"
$culture = [System.Globalization.CultureInfo]::InvariantCulture

$port = [System.IO.Ports.SerialPort]::new(
    $PortName,
    $BaudRate,
    [System.IO.Ports.Parity]::None,
    8,
    [System.IO.Ports.StopBits]::One
)
$port.NewLine = "`r`n"
$port.ReadTimeout = 1
$port.WriteTimeout = 1000
$script:rxBuffer = ""
$script:rxCount = 0
$script:okCount = 0
$script:timeoutCount = 0
$script:stopCount = 0
$script:lastFeedback = ""
$script:lastSeq = 0
$script:lastLeftCount = 0
$script:lastRightCount = 0
$script:lastStatus = ""

function Read-AvailableLines {
    param([System.IO.Ports.SerialPort]$SerialPort)

    if ($SerialPort.BytesToRead -le 0) {
        return
    }

    $script:rxBuffer += $SerialPort.ReadExisting()
    while ($true) {
        $newlineIndex = $script:rxBuffer.IndexOf("`n")
        if ($newlineIndex -lt 0) {
            return
        }

        $line = $script:rxBuffer.Substring(0, $newlineIndex).TrimEnd("`r")
        $script:rxBuffer = $script:rxBuffer.Substring($newlineIndex + 1)
        if ($line.Length -gt 0) {
            $script:rxCount++
            if ($line.StartsWith("FB,")) {
                $parts = $line.Split(",")
                if ($parts.Count -ge 6) {
                    $script:lastFeedback = $line
                    [void][uint32]::TryParse($parts[1], [ref]$script:lastSeq)
                    [void][int32]::TryParse($parts[2], [ref]$script:lastLeftCount)
                    [void][int32]::TryParse($parts[3], [ref]$script:lastRightCount)
                    $script:lastStatus = $parts[5]
                    switch ($parts[5]) {
                        "OK" { $script:okCount++ }
                        "TIMEOUT" { $script:timeoutCount++ }
                        "STOP" { $script:stopCount++ }
                    }
                }
            }

            if ($VerboseLog) {
                Write-Host ("[RX] {0}" -f $line)
            }
        }
    }
}

try {
    $port.Open()
    Write-Host ("Opened {0}. Sending CMD every {1} ms for {2} ms." -f $PortName, $PeriodMs, $DurationMs)
    Write-Host ("Target: left={0} mm/s, right={1} mm/s" -f $LeftMMPS, $RightMMPS)
    if (-not $VerboseLog) {
        Write-Host "Quiet mode: use -VerboseLog to print every TX/RX line."
    }

    $seq = $StartSeq
    $txCount = 0
    $watch = [System.Diagnostics.Stopwatch]::StartNew()
    $nextSendMs = 0.0
    $nextSummaryMs = [double]$SummaryMs

    while ($watch.ElapsedMilliseconds -lt $DurationMs) {
        Read-AvailableLines -SerialPort $port

        if ($watch.Elapsed.TotalMilliseconds -lt $nextSendMs) {
            $sleepMs = [Math]::Min(5, [Math]::Max(1, [int]($nextSendMs - $watch.Elapsed.TotalMilliseconds)))
            Start-Sleep -Milliseconds $sleepMs
            continue
        }

        $left = $LeftMMPS.ToString("0.###", $culture)
        $right = $RightMMPS.ToString("0.###", $culture)
        $cmd = "CMD,$seq,$left,$right"

        if ($VerboseLog) {
            Write-Host ("[TX] {0}" -f $cmd)
        }
        $port.WriteLine($cmd)
        $txCount++
        $seq++
        $nextSendMs += $PeriodMs

        if ($watch.Elapsed.TotalMilliseconds -ge $nextSummaryMs) {
            Write-Host ("[SUM] t={0}ms tx={1} rx={2} ok={3} timeout={4} stop={5} lastSeq={6} counts={7},{8} status={9}" -f `
                $watch.ElapsedMilliseconds,
                $txCount,
                $script:rxCount,
                $script:okCount,
                $script:timeoutCount,
                $script:stopCount,
                $script:lastSeq,
                $script:lastLeftCount,
                $script:lastRightCount,
                $script:lastStatus)
            $nextSummaryMs += $SummaryMs
        }
    }

    if (-not $NoStop) {
        $stop = "STOP,$seq"
        if ($VerboseLog) {
            Write-Host ("[TX] {0}" -f $stop)
        }
        $port.WriteLine($stop)
        Start-Sleep -Milliseconds 100
        Read-AvailableLines -SerialPort $port
    }

    Read-AvailableLines -SerialPort $port
    Write-Host ("[FINAL] tx={0} rx={1} ok={2} timeout={3} stop={4} lastSeq={5} counts={6},{7} status={8}" -f `
        $txCount,
        $script:rxCount,
        $script:okCount,
        $script:timeoutCount,
        $script:stopCount,
        $script:lastSeq,
        $script:lastLeftCount,
        $script:lastRightCount,
        $script:lastStatus)
}
finally {
    if ($port.IsOpen) {
        $port.Close()
    }
}
