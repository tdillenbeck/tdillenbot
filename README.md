# tdillenbot

A Telegram bot daemon that updates a [Rebrandly](https://rebrandly.com) short link to point at a YouTube URL.

## Commands

| Command | Description |
|---|---|
| `/start` | Show help message |
| `/setlink <youtube-url>` | Update the Rebrandly link to the given YouTube URL |

Accepts full URLs (`https://www.youtube.com/watch?v=...`), short URLs (`https://youtu.be/...`), live URLs (`https://youtube.com/live/...`), or bare video IDs.

## CI/CD

Pushes to `main` run tests then deploy automatically via SSH over Tailscale. Pull requests run tests only.

**Required GitHub Secrets** (Settings → Secrets and variables → Actions):

| Secret | Value |
|---|---|
| `TAILSCALE_AUTHKEY` | Ephemeral auth key from [Tailscale admin](https://login.tailscale.com/admin/settings/keys) |
| `SSH_HOST` | CT's Tailscale IP (`100.x.x.x`) or MagicDNS hostname |
| `SSH_USER` | SSH login username on the CT |
| `SSH_PRIVATE_KEY` | Private key whose public half is in the CT's `~/.ssh/authorized_keys` |

For the Tailscale auth key: go to **Settings → Keys → Generate auth key**, enable **Reusable** and **Ephemeral** (ephemeral keys auto-remove the runner node when the job finishes).

## Proxmox CT Setup

Run once inside the CT before the first deploy.

```bash
# Install dependencies
sudo apt update && sudo apt install -y python3 python3-venv git openssh-server

# Create a service account and app directory
sudo useradd -r -s /bin/false tdillenbot
sudo mkdir -p /opt/tdillenbot
sudo chown tdillenbot:tdillenbot /opt/tdillenbot

# Clone the repo
sudo -u tdillenbot git clone https://github.com/tdillenbeck/tdillenbot.git /opt/tdillenbot

# Create virtualenv and install dependencies
sudo -u tdillenbot python3 -m venv /opt/tdillenbot/venv
sudo -u tdillenbot /opt/tdillenbot/venv/bin/pip install -r /opt/tdillenbot/requirements.txt

# Create the secrets file
sudo tee /opt/tdillenbot/.env > /dev/null <<EOF
TELEGRAM_BOT_TOKEN=your_token_here
REBRANDLY_API_KEY=your_key_here
REBRANDLY_LINK_ID=your_link_id_here
EOF
sudo chmod 600 /opt/tdillenbot/.env
sudo chown tdillenbot:tdillenbot /opt/tdillenbot/.env

# Allow the deploy user to restart the service without a password prompt
echo "$USER ALL=(ALL) NOPASSWD: /bin/systemctl restart tdillenbot" | sudo tee /etc/sudoers.d/tdillenbot-deploy

# Install and start the systemd service
sudo cp /opt/tdillenbot/deploy/tdillenbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tdillenbot
```

Check status with `sudo systemctl status tdillenbot` and logs with `journalctl -u tdillenbot -f`.

> **Note:** Proxmox LXC containers require `features: nesting=1` in the CT options for systemd to work correctly. Enable it in the Proxmox web UI under the CT's **Options → Features** before running setup.

## Development

```bash
pip install -r requirements.txt
python -m pytest
```

Set the environment variables from `.env` before running locally:

```bash
export TELEGRAM_BOT_TOKEN=...
export REBRANDLY_API_KEY=...
export REBRANDLY_LINK_ID=...
python tdillenbot.py
```
