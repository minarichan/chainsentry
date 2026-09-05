# Pin deploy/ens-gateway/index.html to IPFS via Pinata.
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_lib.ps1")
Import-DeploySecrets
if (-not $env:PINATA_JWT) {
    Write-Host "Add PINATA_JWT to deploy/secrets.env (Pinata API key JWT, pinFileToIPFS permission)."
    Write-Host "Create it at https://app.pinata.cloud  →  API Keys  →  New Key"
    exit 1
}
$html = Join-Path $PSScriptRoot "ens-gateway\index.html"
if (-not (Test-Path $html)) {
    throw "Missing $html"
}
$py = Join-Path (Get-DeployRoot) ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    $py = "python"
}
Write-Host "Pinning $html to Pinata..."
& $py -c @"
import json, os, sys, urllib.request
from pathlib import Path

html = Path(r'$html')
jwt = os.environ['PINATA_JWT']
boundary = '----ChainsentryPinata'
body = bytearray()

def add_field(name: str, value: str) -> None:
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(f'Content-Disposition: form-data; name=\"{name}\"\r\n\r\n'.encode())
    body.extend(value.encode() + b'\r\n')

def add_file(name: str, filename: str, data: bytes, filepath: str) -> None:
    body.extend(f'--{boundary}\r\n'.encode())
    body.extend(
        f'Content-Disposition: form-data; name=\"{name}\"; filename=\"{filepath}\"\r\n'.encode()
    )
    body.extend(b'Content-Type: text/html\r\n\r\n')
    body.extend(data + b'\r\n')

add_file('file', 'index.html', html.read_bytes(), 'index.html')
add_field('pinataMetadata', json.dumps({'name': 'chainsentry-ens-gateway'}))
add_field('pinataOptions', json.dumps({'cidVersion': 1}))
body.extend(f'--{boundary}--\r\n'.encode())

req = urllib.request.Request(
    'https://api.pinata.cloud/pinning/pinFileToIPFS',
    data=bytes(body),
    method='POST',
    headers={
        'Authorization': 'Bearer ' + jwt,
        'Content-Type': f'multipart/form-data; boundary={boundary}',
    },
)
try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode()
except urllib.error.HTTPError as exc:
    raw = exc.read().decode()
    print(raw)
    sys.exit(1)
print(raw)
parsed = json.loads(raw)
cid = parsed.get('IpfsHash')
if not cid:
    sys.exit(1)
print()
print('Pinned. ENS contenthash:')
print('ipfs://' + cid)
print('Check: https://' + cid + '.ipfs.dweb.link/')
print('Then https://chainsentry.eth.limo')
old = 'bafybeiekz3vtezn7wrgp4fum5nf4lwtxcqz3d2cbukc4is737vziaazztm'
if cid != old:
    print('This CID differs from the one already on chainsentry.eth. Update the contenthash in the ENS app and save.')
"@
