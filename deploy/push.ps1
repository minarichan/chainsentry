# Upload this tree to the VPS and rebuild the container.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
Import-DeploySecrets
$ssh = Get-SshArgs
$scp = Get-ScpArgs
$target = Get-SshTarget
$remote = $env:REMOTE_DIR
$root = Get-DeployRoot
$tar = Join-Path $env:TEMP "chainsentry-deploy.tgz"

$excludes = @(
    "--exclude=.git",
    "--exclude=.venv",
    "--exclude=frontend/node_modules",
    "--exclude=frontend/dist",
    "--exclude=__pycache__",
    "--exclude=.pytest_cache",
    "--exclude=data/*.sqlite",
    "--exclude=deploy/secrets.env"
)

Push-Location $root
try {
    tar -czf $tar @excludes .
} finally {
    Pop-Location
}

Write-Host "Uploading to ${target}:${remote}"
scp @scp $tar "${target}:/tmp/chainsentry-deploy.tgz"
ssh @ssh $target "mkdir -p $remote; tar -xzf /tmp/chainsentry-deploy.tgz -C $remote; rm /tmp/chainsentry-deploy.tgz"
Remove-Item $tar -Force

if ($env:PUBLIC_URL) {
    $line = "PUBLIC_URL=$($env:PUBLIC_URL)"
    ssh @ssh $target "grep -v PUBLIC_URL= $remote/.env > $remote/.env.tmp; mv $remote/.env.tmp $remote/.env; echo $line >> $remote/.env"
}

Write-Host "Rebuilding..."
ssh @ssh $target "cd $remote; docker compose -f deploy/compose.yml up -d --build"
ssh @ssh $target "curl -sS http://127.0.0.1:8000/health"
Write-Host ""
Write-Host ("Verify: {0}" -f $env:PUBLIC_URL)
