# Create an Ed25519 key for the VPS and write its path into deploy/secrets.env.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$sshDir = Join-Path $env:USERPROFILE ".ssh"
New-Item -ItemType Directory -Force -Path $sshDir | Out-Null
$key = Join-Path $sshDir "chainsentry_ed25519"
if (-not (Test-Path $key)) {
    ssh-keygen -t ed25519 -f $key -N '""' -C "chainsentry-vps"
    Write-Host "Created $key"
} else {
    Write-Host "Using existing $key"
}

$secrets = Join-Path $PSScriptRoot "secrets.env"
$example = Join-Path $PSScriptRoot "secrets.env.example"
if (-not (Test-Path $secrets)) {
    Copy-Item $example $secrets
    Write-Host "Created $secrets from the example — fill VPS_HOST."
}

$raw = Get-Content $secrets -Raw
if ($raw -match "(?m)^SSH_KEY_PATH=") {
    $raw = [regex]::Replace($raw, "(?m)^SSH_KEY_PATH=.*$", "SSH_KEY_PATH=$key")
} else {
    $raw = $raw.TrimEnd() + "`r`nSSH_KEY_PATH=$key`r`n"
}
Set-Content -Path $secrets -Value $raw -NoNewline
Write-Host "SSH_KEY_PATH set in deploy/secrets.env"
Write-Host "Public key:"
Get-Content "$key.pub"
Write-Host "Add that line to /root/.ssh/authorized_keys on the VPS, then run deploy/bootstrap.ps1"
