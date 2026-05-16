#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/tdillenbeck/tdillenbot.git"
APP_DIR="/opt/tdillenbot"
SERVICE_USER="tdillenbot"
SERVICE_FILE="/etc/systemd/system/tdillenbot.service"

info()  { echo "[+] $*"; }
warn()  { echo "[!] $*"; }
fatal() { echo "[x] $*" >&2; exit 1; }

[[ $EUID -ne 0 ]] && fatal "Run this script as root (or with sudo)"

# Install system dependencies
info "Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv git openssh-server

# Create service account
if id "$SERVICE_USER" &>/dev/null; then
    info "Service account '$SERVICE_USER' already exists, skipping"
else
    info "Creating service account '$SERVICE_USER'..."
    useradd -r -s /bin/false "$SERVICE_USER"
fi

# Create app directory
info "Setting up app directory at $APP_DIR..."
mkdir -p "$APP_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

# Clone or update the repo
if [[ -d "$APP_DIR/.git" ]]; then
    info "Repo already cloned, pulling latest..."
    sudo -u "$SERVICE_USER" git -C "$APP_DIR" pull origin main
else
    info "Cloning repo..."
    sudo -u "$SERVICE_USER" git clone "$REPO_URL" "$APP_DIR"
fi

# Create virtualenv
if [[ -d "$APP_DIR/venv" ]]; then
    info "Virtualenv already exists, skipping"
else
    info "Creating virtualenv..."
    sudo -u "$SERVICE_USER" python3 -m venv "$APP_DIR/venv"
fi

info "Installing Python dependencies..."
sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

# Create .env file
if [[ -f "$APP_DIR/.env" ]]; then
    warn ".env already exists at $APP_DIR/.env — skipping. Edit it manually if needed."
else
    info "Creating .env file (you'll need these values from Telegram and Rebrandly)..."
    read -rp "  TELEGRAM_BOT_TOKEN: " telegram_token
    read -rp "  REBRANDLY_API_KEY:   " rebrandly_key
    read -rp "  REBRANDLY_LINK_ID:   " rebrandly_link_id

    cat > "$APP_DIR/.env" <<EOF
TELEGRAM_BOT_TOKEN=${telegram_token}
REBRANDLY_API_KEY=${rebrandly_key}
REBRANDLY_LINK_ID=${rebrandly_link_id}
EOF
    chmod 600 "$APP_DIR/.env"
    chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR/.env"
fi

# Sudoers entry for the deploy SSH user
DEPLOY_USER="${SUDO_USER:-$USER}"
SUDOERS_FILE="/etc/sudoers.d/tdillenbot-deploy"
if [[ -f "$SUDOERS_FILE" ]]; then
    info "Sudoers entry already exists, skipping"
else
    info "Granting $DEPLOY_USER passwordless restart of tdillenbot service..."
    echo "$DEPLOY_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart tdillenbot" > "$SUDOERS_FILE"
    chmod 440 "$SUDOERS_FILE"
fi

# Install systemd service
info "Installing systemd service..."
cp "$APP_DIR/deploy/tdillenbot.service" "$SERVICE_FILE"

# Set the service User= to the service account
sed -i "s/^User=.*/User=$SERVICE_USER/" "$SERVICE_FILE"

systemctl daemon-reload
systemctl enable tdillenbot
systemctl restart tdillenbot

echo ""
info "Setup complete."
info "Status:  systemctl status tdillenbot"
info "Logs:    journalctl -u tdillenbot -f"
