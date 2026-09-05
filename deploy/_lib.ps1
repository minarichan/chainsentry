function Get-DeployRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Import-DeploySecrets {
    $path = Join-Path $PSScriptRoot "secrets.env"
    if (-not (Test-Path $path)) {
        throw "Missing deploy/secrets.env. Copy deploy/secrets.env.example and fill it in."
    }
    Get-Content $path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) { return }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { return }
        $name = $line.Substring(0, $eq).Trim()
        $value = $line.Substring($eq + 1).Trim().Trim("'").Trim('"')
        Set-Item -Path "Env:$name" -Value $value
    }
    foreach ($required in @("VPS_HOST", "VPS_USER", "SSH_KEY_PATH", "REMOTE_DIR")) {
        if (-not (Get-Item "Env:$required" -ErrorAction SilentlyContinue).Value) {
            throw "deploy/secrets.env is missing $required"
        }
    }
}

function Get-SshKey {
    $key = $env:SSH_KEY_PATH
    if (-not (Test-Path $key)) {
        throw "SSH key not found: $key"
    }
    return $key
}

function Get-SshPort {
    if ($env:VPS_PORT) { return $env:VPS_PORT }
    return "22"
}

function Get-SshArgs {
    return @(
        "-i", (Get-SshKey),
        "-p", (Get-SshPort),
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=accept-new"
    )
}

function Get-ScpArgs {
    return @(
        "-i", (Get-SshKey),
        "-P", (Get-SshPort),
        "-o", "IdentitiesOnly=yes",
        "-o", "StrictHostKeyChecking=accept-new"
    )
}

function Get-SshTarget {
    return ($env:VPS_USER + "@" + $env:VPS_HOST)
}
