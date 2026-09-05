# Show local deploy secrets. The file never leaves this PC via git.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$path = Join-Path $PSScriptRoot "secrets.env"
if (-not (Test-Path $path)) {
    Write-Host "No deploy/secrets.env yet. Copy the example:"
    Write-Host "  copy deploy\secrets.env.example deploy\secrets.env"
    exit 1
}
Write-Host "=== $path ==="
Get-Content $path
Write-Host "=== SSH public key (safe to paste into the VPS) ==="
. (Join-Path $PSScriptRoot "_lib.ps1")
Import-DeploySecrets
$pub = "$($env:SSH_KEY_PATH).pub"
if (Test-Path $pub) { Get-Content $pub } else { Write-Host "No .pub next to SSH_KEY_PATH" }
