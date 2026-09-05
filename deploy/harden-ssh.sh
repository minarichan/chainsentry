#!/bin/bash
# Disable password SSH. Run on the VPS as root ONLY after you can log in with the key.
#   ssh -i <key> root@HOST 'bash -s' < deploy/harden-ssh.sh
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

AUTH_KEYS=/root/.ssh/authorized_keys
if [[ ! -s "$AUTH_KEYS" ]]; then
  echo "No $AUTH_KEYS — aborting so you are not locked out." >&2
  exit 1
fi

SSHD=/etc/ssh/sshd_config
cp -a "$SSHD" "${SSHD}.bak.$(date +%Y%m%d%H%M%S)"

mkdir -p /etc/ssh/sshd_config.d
cat >/etc/ssh/sshd_config.d/50-chainsentry-hardening.conf <<'EOF'
PermitRootLogin prohibit-password
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PubkeyAuthentication yes
AuthenticationMethods publickey
X11Forwarding no
AllowTcpForwarding no
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

# Neutralize any leftover yes in the main config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "$SSHD"
sed -i 's/^#\?KbdInteractiveAuthentication.*/KbdInteractiveAuthentication no/' "$SSHD"
sed -i 's/^#\?ChallengeResponseAuthentication.*/ChallengeResponseAuthentication no/' "$SSHD"
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' "$SSHD"

sshd -t
if command -v systemctl >/dev/null 2>&1; then
  systemctl reload sshd || systemctl reload ssh
else
  service ssh reload
fi

echo "Password SSH is off. Keep your private key; it is the only login."
