$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:STATE_MODE = 'local'
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$python = (Get-Command py -ErrorAction Stop).Source
# Windows PowerShell 5.1 wraps native stderr as a non-terminating error. Python logs
# to stderr, so allow the process to finish and use its exit code as the task result.
$ErrorActionPreference = 'Continue'
& $python -3 (Join-Path $root 'bot.py') *>> (Join-Path $logDir 'poll.log')
exit $LASTEXITCODE
