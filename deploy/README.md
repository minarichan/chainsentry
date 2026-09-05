# ChainSentry on InterServer (not Railway)

One Docker image serves the React UI and FastAPI (`Dockerfile`). Browser routes stay hashed: `/#/`, `/#/report/<id>`, `/#/settings`. The server never sees the hash.

You must run the PowerShell scripts **on your PC** with `deploy/secrets.env` filled in. This environment cannot log into InterServer or sign ENS transactions for you.

## Honest limits

| Want | Reality |
|---|---|
| `https://chainsentry.dev` | DNS + Cloudflare HTTPS. The app still runs on the VPS. |
| `chainsentry.eth` in Chrome | Not a DNS hostname. Use `chainsentry.dev`, or `eth.limo` after `contenthash` is set. |
| `https://chainsentry.eth.limo` | eth.limo serves **IPFS `contenthash`**, not FastAPI. Pin `deploy/ens-gateway/` so it bounces to `.dev`. |
| `https://chainsentry.eth.link` | Cloudflare shut this gateway down. Do not rely on it. |
| Brave / Opera address bar | They resolve **on-chain `contenthash`** (IPFS). Same bounce page. They do not run your Python API. |

## 1. Secrets on this PC

```powershell
copy deploy\secrets.env.example deploy\secrets.env
notepad deploy\secrets.env
powershell -File deploy\new-ssh-key.ps1
powershell -File deploy\show-secrets.ps1
```

`deploy/secrets.env` is gitignored. That is the file to open whenever you need the host, user, key path, or public URL. Do not commit it.

App secrets (`ETHERSCAN_API_KEY`, RPC URLs) stay in the repo-root **`.env`** (also gitignored). Copy `.env.example` → `.env`. Leave `ETHERSCAN_API_KEY` empty on the public VPS; visitors can still paste a key in Settings.

## 2. Backup this PC

```powershell
powershell -File deploy\backup-pc.ps1
```

Writes a dated folder under `BACKUP_DIR` plus `_secrets` (SSH key + env files).

## 3. InterServer first login

From the InterServer panel: note the **IPv4**. First login is usually `root` + panel password. Put the IP in `VPS_HOST`.

In the panel (or SSH once with the password), append your **public** key to `/root/.ssh/authorized_keys`. Then:

```powershell
powershell -File deploy\bootstrap.ps1
```

That installs Docker, UFW (22/80/443), fail2ban, uploads the tree, and starts `deploy/compose.yml` (2 GiB VPS: container capped at 1536m, data volume `/app/data`).

Confirm: `http://YOUR_IP/health` and `http://YOUR_IP/#/`.

## 4. SSH keys only

```powershell
powershell -File deploy\harden-ssh.ps1
```

Password SSH is then off. Clear `VPS_PASSWORD` in `secrets.env`.

## 5. Push from this PC

```powershell
powershell -File deploy\push.ps1
```

Live rebuilds while you edit:

```powershell
powershell -File deploy\watch.ps1
```

Saves debounce 8s, then upload + `docker compose up --build`. Do not point this at `data/*.sqlite` on the server (excluded) so production reports are not overwritten.

Optional git remote: `git remote add vps ssh://root@HOST:/opt/chainsentry.git` after the post-receive hook is in place (`bootstrap.ps1` installs it).

## 6. Cloudflare DNS + HTTPS (`chainsentry.dev`)

Zone is already on Cloudflare. Origin is HTTP on the VPS (`:80` → container `:8000`). Cloudflare terminates HTTPS at the edge.

1. **DNS → Records** → Import BIND `deploy/cloudflare-bind.txt`, or add:
   - Type **A**, Name `@`, IPv4 `162.35.168.32`, **Proxied** (orange)
   - Type **CNAME**, Name `www`, Target `chainsentry.dev`, **Proxied**
2. **SSL/TLS → Overview** → encryption mode **Flexible** (origin has no certificate yet). **Full (strict)** will 525 until you add an origin cert.
3. **SSL/TLS → Edge Certificates** → **Always Use HTTPS** On.
4. On this PC, `PUBLIC_URL=https://chainsentry.dev` in `deploy/secrets.env`, then `deploy/push.ps1`.

Optional later: named tunnel (`CLOUDFLARE_TUNNEL_TOKEN`) if you want the origin off the public internet. Not required for `.dev`.

## 7. ENS (`chainsentry.eth`)

In [app.ens.domains](https://app.ens.domains) as the name owner:

| Record | Value |
|---|---|
| `url` | `https://chainsentry.dev` (no hash; the app adds `/#/`) |
| description | Security scanner for the on-chain stack |
| `contenthash` | `ipfs://<directory CID>` of `deploy/ens-gateway/` (index.html already bounces to `.dev`) |

Pin the HTML with any IPFS pinning service you already use, then set `contenthash`. After that:

- ENS-aware browsers that fetch `contenthash` open the bounce page, then the VPS app.
- `https://chainsentry.eth.limo` does the same **if** `contenthash` is set.
- Wallets show the `url` record.

The scanner itself always runs on the VPS origin. Hash routes are unchanged.

## 8. Turn off Railway

Delete the Railway **web** service (or the project) in the Railway dashboard so deploys stop. `railway.json` is removed from this repo.

## 9. Compose commands on the VPS

```bash
cd /opt/chainsentry
docker compose -f deploy/compose.yml up -d --build
docker compose -f deploy/compose.yml logs -f web
docker volume inspect chainsentry_chainsentry-data
```
