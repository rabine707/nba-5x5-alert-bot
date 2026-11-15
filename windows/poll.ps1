$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:STATE_MODE = 'local'
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$python = (Get-Command py -ErrorAction Stop).Source
# Windows PowerShell 5.1 wraps native stderr as ErrorRecord. Python logs to
# stderr, so normalize those records and let its exit code control the task.
$ErrorActionPreference = 'Continue'
& $python -3 (Join-Path $root 'bot.py') 2>&1 |
    ForEach-Object {
        if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message }
        else { $_ }
    } | Out-File -FilePath (Join-Path $logDir 'poll.log') -Append -Encoding utf8
exit $LASTEXITCODE
