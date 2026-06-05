#!/usr/bin/env bash
# Xeon direct-WSL-ssh, PART 1 (WSL-side). Run via: ssh xeon "wsl -d Ubuntu-24.04
# -- bash /mnt/carc-shared/code_sync/xeon_wsl_sshd_setup.sh". Passwordless sudo
# confirmed. Installs sshd in WSL on port 2222 (key-only) so the box can be
# reached WITHOUT the cmd.exe hop. Idempotent.
set -e
PUBKEY='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBSQKjj9/sKrkwhtzVGb6nU2wFKCkQnZpt1VlDFi2npw jishal@gmail.com'
echo "=== apt install openssh-server ==="
sudo apt-get update -y -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openssh-server
echo "=== generate host keys ==="; sudo ssh-keygen -A
echo "=== sshd_config: Port 2222 + key-only ==="
S=/etc/ssh/sshd_config
sudo sed -i 's/^#\?Port .*/Port 2222/' "$S"
sudo grep -q '^Port 2222' "$S" || echo 'Port 2222' | sudo tee -a "$S" >/dev/null
sudo sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' "$S"
sudo sed -i 's/^#\?PubkeyAuthentication .*/PubkeyAuthentication yes/' "$S"
echo "=== authorized_keys (5800x key) ==="
mkdir -p ~/.ssh && chmod 700 ~/.ssh
grep -qF "$PUBKEY" ~/.ssh/authorized_keys 2>/dev/null || echo "$PUBKEY" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
echo "=== enable + restart ssh ==="
sudo systemctl enable ssh
sudo systemctl restart ssh
sleep 1
echo -n "ssh active: "; systemctl is-active ssh || true
echo "=== listening on 2222? ==="; sudo ss -tlnp 2>/dev/null | grep ':2222' || echo "WARN: not listening on 2222"
echo "=== WSL-SIDE DONE ==="
