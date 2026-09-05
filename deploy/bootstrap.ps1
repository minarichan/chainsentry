# First push: install Docker on the VPS, upload the repo, start the app.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
Import-DeploySecrets
$ssh = Get-SshArgs
$scp = Get-ScpArgs
$target = Get-SshTarget
$remote = $env:REMOTE_DIR
$root = Get-DeployRoot

Write-Host "Installing Docker / firewall on $target ..."
Get-Content (Join-Path $PSScriptRoot "setup-vps.sh") -Raw | ssh @ssh $target "sed 's/\r$//' | bash -s"

ssh @ssh $target "mkdir -p $remote"

$envSrc = Join-Path $root ".env"
if (Test-Path $envSrc) {
    scp @scp $envSrc "${target}:${remote}/.env"
} else {
    Write-Host "No local .env - copying .env.example to the VPS."
    scp @scp (Join-Path $root ".env.example") "${target}:${remote}/.env"
}

if ($env:PUBLIC_URL) {
    $line = "PUBLIC_URL=$($env:PUBLIC_URL)"
    ssh @ssh $target "grep -v PUBLIC_URL= $remote/.env > $remote/.env.tmp; mv $remote/.env.tmp $remote/.env; echo $line >> $remote/.env"
}

& powershell -NoProfile -File (Join-Path $PSScriptRoot "push.ps1")

$hookB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((Get-Content (Join-Path $PSScriptRoot "git-hook-post-receive") -Raw)))
$hookCmd = "echo $hookB64 | base64 -d > /opt/chainsentry.git/hooks/post-receive; chmod +x /opt/chainsentry.git/hooks/post-receive; sed -i s/\r// /opt/chainsentry.git/hooks/post-receive $remote/deploy/*.sh"
ssh @ssh $target $hookCmd

Write-Host "When the app answers, run: powershell -File deploy/harden-ssh.ps1"
Write-Host ('Open ' + $env:PUBLIC_URL)
