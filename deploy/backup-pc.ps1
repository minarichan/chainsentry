# Copy the project (and local .env / deploy secrets) to BACKUP_DIR on this PC.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
Import-DeploySecrets
$root = Get-DeployRoot
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$destRoot = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path $env:USERPROFILE "Documents\ChainSentry-backup" }
$dest = Join-Path $destRoot $stamp
New-Item -ItemType Directory -Force -Path $dest | Out-Null

robocopy $root $dest /E /XD .git .venv node_modules dist __pycache__ .pytest_cache /XF *.pyc /NFL /NDL /NJH /NJS /nc /ns /np
if ($LastExitCode -ge 8) { throw "robocopy failed with $LastExitCode" }

$secretDir = Join-Path $dest "_secrets"
New-Item -ItemType Directory -Force -Path $secretDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot "secrets.env") (Join-Path $secretDir "secrets.env") -ErrorAction SilentlyContinue
$envFile = Join-Path $root ".env"
if (Test-Path $envFile) { Copy-Item $envFile (Join-Path $secretDir "app.env") }
$key = $env:SSH_KEY_PATH
if ($key -and (Test-Path $key)) {
    Copy-Item $key (Join-Path $secretDir "chainsentry_ed25519")
    Copy-Item "$key.pub" (Join-Path $secretDir "chainsentry_ed25519.pub") -ErrorAction SilentlyContinue
}

Write-Host "Backup written to $dest"
Write-Host "Secrets are in $secretDir. Keep that folder off USB sticks you share."
