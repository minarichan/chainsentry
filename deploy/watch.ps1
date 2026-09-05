# Watch the repo and push to the VPS after files settle (8s debounce).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
$root = Get-DeployRoot
$push = Join-Path $PSScriptRoot "push.ps1"
$last = Get-Date
$dirty = $true

Write-Host "Watching $root — save a file, wait 8s, VPS rebuilds. Ctrl+C to stop."

while ($true) {
    $newest = Get-ChildItem -Path $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notmatch '\\(\.git|\.venv|node_modules|__pycache__|\.pytest_cache)\\' -and
            $_.FullName -notmatch 'frontend\\dist\\' -and
            $_.Name -ne "secrets.env"
        } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($newest -and $newest.LastWriteTime -gt $last) {
        $last = $newest.LastWriteTime
        $dirty = $true
    }
    if ($dirty -and ((Get-Date) - $last).TotalSeconds -ge 8) {
        $dirty = $false
        Write-Host "$(Get-Date -Format o) pushing after $($newest.FullName)"
        & powershell -NoProfile -File $push
    }
    Start-Sleep -Seconds 2
}
