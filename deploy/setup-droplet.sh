#!/usr/bin/env bash
set -euo pipefail

# One-time provisioning script for Ubuntu 24.04 droplet.
# Idempotent: safe to re-run.

if [ "$(id -u)" -ne 0 ]; then
  echo "This script must be run as root. Exiting." >&2
  exit 1
fi

REPO_URL="https://github.com/sireenmalik/carrier-voice-agent.git"
DEST_DIR="/opt/carrier-voice-agent"
DEPLOY_USER="deploy"
ENV_FILE="/etc/carrier-voice-agent.env"
VENV_DIR="$DEST_DIR/.venv"

export DEBIAN_FRONTEND=noninteractive

echo "Updating apt..."
apt-get update -y

echo "Installing base packages..."
apt-get install -y software-properties-common ca-certificates curl gnupg lsb-release

# Python 3.12 on Ubuntu 24.04
echo "Installing Python 3.12 and tools..."
apt-get install -y python3.12 python3.12-venv python3-pip git nginx ufw certbot python3-certbot-nginx

# Node.js 20 via NodeSource
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | sed 's/v//')" != "20" ]; then
  echo "Installing Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
else
  echo "Node.js already installed"
fi

# Create deploy user if necessary
if ! id -u "$DEPLOY_USER" >/dev/null 2>&1; then
  echo "Creating user $DEPLOY_USER"
  adduser --disabled-password --gecos "Deploy user" $DEPLOY_USER
fi

# Clone or update repository
if [ ! -d "$DEST_DIR/.git" ]; then
  echo "Cloning repository to $DEST_DIR"
  rm -rf "$DEST_DIR"
  git clone "$REPO_URL" "$DEST_DIR"
  chown -R $DEPLOY_USER:$DEPLOY_USER "$DEST_DIR"
else
  echo "Repository already present at $DEST_DIR — fetching latest"
  git -C "$DEST_DIR" fetch --all --tags
  git -C "$DEST_DIR" reset --hard origin/main || true
  chown -R $DEPLOY_USER:$DEPLOY_USER "$DEST_DIR"
fi

# Environment file
if [ ! -f "$ENV_FILE" ]; then
  echo "Creating empty environment file at $ENV_FILE (fill BEDROCK_MODEL_ID_TEXT and AWS_REGION as needed)"
  : > "$ENV_FILE"
  chmod 640 "$ENV_FILE"
fi

# Create venv and install Python requirements
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating Python venv at $VENV_DIR"
  sudo -u $DEPLOY_USER python3.12 -m venv "$VENV_DIR"
fi

echo "Installing Python requirements into venv"
# Use pip from the venv
$VENV_DIR/bin/pip install --upgrade pip
$VENV_DIR/bin/pip install -r "$DEST_DIR/requirements.txt"

# Build frontend as deploy user
echo "Building frontend"
cd "$DEST_DIR/frontend"
# Ensure node modules installed and build (idempotent enough)
sudo -u $DEPLOY_USER npm ci
sudo -u $DEPLOY_USER npm run build

# Install systemd service
SERVICE_FILE="/etc/systemd/system/carrier-voice-agent.service"
if [ ! -f "$SERVICE_FILE" ]; then
  cat > "$SERVICE_FILE" <<'SERVICE'
[Unit]
Description=Carrier Voice Agent (uvicorn)
After=network.target

[Service]
Type=simple
User=deploy
Group=deploy
WorkingDirectory=/opt/carrier-voice-agent
EnvironmentFile=/etc/carrier-voice-agent.env
ExecStart=/opt/carrier-voice-agent/.venv/bin/uvicorn api.server:app --host 127.0.0.1 --port 8080 --log-level info
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
SERVICE
  systemctl daemon-reload
  systemctl enable carrier-voice-agent.service
fi

# Nginx site
NGINX_SITE="/etc/nginx/sites-available/carrier-voice-agent"
NGINX_LINK="/etc/nginx/sites-enabled/carrier-voice-agent"
if [ ! -f "$NGINX_SITE" ]; then
  cat > "$NGINX_SITE" <<'NGINX'
# carrier-voice-agent nginx site
# NOTE: proxy_buffering off is REQUIRED for Server-Sent Events (SSE) to stream correctly.
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name _;

    root /opt/carrier-voice-agent/frontend/dist;
    index index.html;

    # Serve static assets directly
    location /assets/ {
        try_files $uri =404;
    }

    # Reverse proxy API and SSE endpoints to local uvicorn
    location /turn {
        proxy_pass http://127.0.0.1:8080/turn;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off; # critical for SSE
        proxy_read_timeout 3600s;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_buffering off; # critical for SSE
        proxy_read_timeout 3600s;
    }

    # SPA fallback
    location / {
        try_files $uri /index.html;
    }
}
NGINX
  fi

if [ ! -L "$NGINX_LINK" ]; then
  # Remove default nginx site if present so our site becomes the default
  rm -f /etc/nginx/sites-enabled/default
  ln -s "$NGINX_SITE" "$NGINX_LINK"
fi

# Test nginx config and reload
nginx -t
systemctl reload nginx

# UFW
if command -v ufw >/dev/null 2>&1; then
  ufw allow OpenSSH || true
  ufw allow 80/tcp || true
  ufw --force enable || true
fi

# Start the service
systemctl daemon-reload
systemctl restart carrier-voice-agent.service || true
systemctl restart nginx || true

IP_ADDR="$(curl -sSf https://ifconfig.me || echo '<droplet-ip>')"

echo "Setup complete. Visit: http://$IP_ADDR/"
