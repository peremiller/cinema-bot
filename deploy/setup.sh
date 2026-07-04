#!/usr/bin/env bash
# One-shot installer for the Cinema Finder bot on an Ubuntu VM (Oracle Cloud
# Always-Free, or any Linux box). Idempotent: safe to re-run to update.
#
#   curl -fsSL https://raw.githubusercontent.com/peremiller/cinema-bot/main/deploy/setup.sh | bash
#
# Requires: /opt/cinema-bot/.env to exist with TELEGRAM_BOT_TOKEN and TMDB_API_KEY
# (the script pauses and tells you how to create it if it's missing).
set -euo pipefail

REPO="https://github.com/peremiller/cinema-bot.git"
DIR="/opt/cinema-bot"
ME="$(whoami)"

echo "==> Installing system packages"
sudo apt-get update -y
sudo apt-get install -y git python3 python3-venv python3-pip fonts-dejavu-core

echo "==> Setting timezone to Asia/Manila (so /subscribe HH:MM is your local time)"
sudo timedatectl set-timezone Asia/Manila || true

echo "==> Fetching code into $DIR"
sudo mkdir -p "$DIR"
sudo chown "$ME":"$ME" "$DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull --ff-only
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

if [ ! -f "$DIR/.env" ]; then
  cat <<MSG

  !! Missing $DIR/.env — create it, then re-run this script:

     nano $DIR/.env

  Paste (with your real values):

     TELEGRAM_BOT_TOKEN=your-telegram-token
     TMDB_API_KEY=your-tmdb-key

MSG
  exit 1
fi

echo "==> Python virtualenv + dependencies"
python3 -m venv .venv
./.venv/bin/pip install -U pip
./.venv/bin/pip install -r requirements.txt

echo "==> Installing systemd service"
sudo tee /etc/systemd/system/cinema-bot.service >/dev/null <<UNIT
[Unit]
Description=Cinema Finder Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$ME
WorkingDirectory=$DIR
ExecStart=$DIR/.venv/bin/python $DIR/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now cinema-bot
sleep 2
sudo systemctl status cinema-bot --no-pager || true

echo
echo "==> Done. The bot now runs 24/7 and restarts on crash/reboot."
echo "    Logs:    journalctl -u cinema-bot -f"
echo "    Restart: sudo systemctl restart cinema-bot"
echo
echo "    IMPORTANT: stop the copy on your Mac so only one instance polls:"
echo "    launchctl unload ~/Library/LaunchAgents/com.cinemabot.plist"
