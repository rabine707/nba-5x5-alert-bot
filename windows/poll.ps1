$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:STATE_MODE = 'local'
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$python = (Get-Command py -ErrorAction Stop).Source
& $python -3 (Join-Path $root 'bot.py') *>> (Join-Path $logDir 'poll.log')
exit $LASTEXITCODE
