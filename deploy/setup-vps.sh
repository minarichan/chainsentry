#!/bin/bash
# Run once on the InterServer VPS as root after the first SSH login.
#   curl/scp this file, then: bash setup-vps.sh
set -euo pipefail

APP=/opt/chainsentry
if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git ufw fail2ban

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

install -d -m 0755 "$APP"
install -d -m 0755 /opt/chainsentry.git
if [[ ! -d /opt/chainsentry.git/objects ]]; then
  git init --bare /opt/chainsentry.git
fi

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

cat >/etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 4
bantime = 1h
EOF
systemctl enable --now fail2ban || echo "fail2ban skipped"

echo "VPS base install done. Next: copy the repo, create $APP/.env, then:"
echo "  docker compose -f $APP/deploy/compose.yml --env-file $APP/.env up -d --build"
echo "Then run $APP/deploy/harden-ssh.sh AFTER your SSH key works."
