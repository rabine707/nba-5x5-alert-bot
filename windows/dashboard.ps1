$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = (Get-Command py -ErrorAction Stop).Source
& $python -3 (Join-Path $root 'dashboard.py')
