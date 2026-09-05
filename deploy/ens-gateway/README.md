# ENS / IPFS bounce page

`index.html` redirects to `https://chainsentry.dev/#/`. Pin this **directory** (so gateways serve `/` as the HTML), then set `chainsentry.eth` `contenthash` to `ipfs://<cid>`.

Pinned on Pinata. Set ENS `contenthash` to:

`ipfs://bafkreibngk76l67765tvwuxteklgemp6jguz5wzpen4au43ohz65lmojga`

Re-pin with `powershell -File deploy/pin-ens-gateway.ps1` (needs `PINATA_JWT` in `deploy/secrets.env`).
