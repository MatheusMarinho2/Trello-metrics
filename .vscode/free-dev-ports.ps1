$ErrorActionPreference = "SilentlyContinue"

$workspace = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ports = @(8000, 5173, 5174)
$targetPids = New-Object System.Collections.Generic.HashSet[int]

foreach ($port in $ports) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique |
        ForEach-Object {
            if ($_ -and $_ -ne $PID) {
                [void]$targetPids.Add([int]$_)
            }
        }
}

Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -and
        $_.CommandLine.Contains($workspace) -and
        ($_.CommandLine -match "manage\.py.*runserver" -or $_.CommandLine -match "\bvite\b")
    } |
    ForEach-Object {
        if ($_.ProcessId -and $_.ProcessId -ne $PID) {
            [void]$targetPids.Add([int]$_.ProcessId)
        }
    }

foreach ($targetPid in $targetPids) {
    Stop-Process -Id $targetPid -Force
}

Start-Sleep -Milliseconds 500
