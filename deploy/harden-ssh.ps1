# Disable password SSH on the VPS. Requires working key login.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
Import-DeploySecrets
$ssh = Get-SshArgs
$target = Get-SshTarget
Get-Content (Join-Path $PSScriptRoot "harden-ssh.sh") -Raw | ssh @ssh $target "sed 's/\r$//' | bash -s"
Write-Host "Clear VPS_PASSWORD in deploy/secrets.env — it is unused now."
