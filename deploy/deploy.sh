#!/usr/bin/env bash
set -euo pipefail

# Redeploy script — intended to be run as the 'deploy' user.
# Idempotent and safe to run repeatedly.

REPO_DIR="/opt/carrier-voice-agent"
VENV_DIR="$REPO_DIR/.venv"
SERVICE_NAME="carrier-voice-agent"

if [ "$(id -un)" = "root" ]; then
  echo "This script should be run as the 'deploy' user, not root. Use sudo -u deploy ./deploy.sh" >&2
  exit 1
fi

cd "$REPO_DIR"

# Ensure working tree is clean-ish, then pull latest
git fetch --all --tags
git reset --hard origin/main

# Update python dependencies (pip will skip already installed)
if [ -x "$VENV_DIR/bin/pip" ]; then
  echo "Installing Python requirements into venv"
  "$VENV_DIR/bin/pip" install -r requirements.txt
else
  echo "Virtualenv not found at $VENV_DIR. Exiting." >&2
  exit 1
fi

# Rebuild frontend
cd frontend
npm ci
npm run build
cd ..

# Restart the service
sudo systemctl restart $SERVICE_NAME

echo "Redeploy complete."
