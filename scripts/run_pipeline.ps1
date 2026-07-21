param(
  [Parameter(Mandatory=$true)][string]$Config,
  [string]$RunId,
  [int]$MaxRecords = 0
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$ArgsList = @("pipeline", "--config", $Config)
if ($RunId) { $ArgsList += @("--run-id", $RunId) }
if ($MaxRecords -gt 0) { $ArgsList += @("--max-records", $MaxRecords) }
& .\.venv\Scripts\openalex-review.exe @ArgsList
