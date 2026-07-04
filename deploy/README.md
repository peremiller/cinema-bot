# Deploying Cinema Finder to an always-on server (Oracle Cloud Free)

The bot must run on a machine that's always on. These steps put it on an Oracle
Cloud **Always Free** VM so it runs 24/7, independent of your laptop.

## 1. Create the free VM (one time, in Oracle's console)
1. Sign up at <https://www.oracle.com/cloud/free/> (Always Free — needs a card for
   identity verification but isn't charged for Always-Free resources).
2. **Create a Compute instance**:
   - Image/shape: **Ubuntu 22.04 (or 24.04)**. Either "Ampere (Arm)" Always-Free
     or "AMD Micro" Always-Free is fine.
   - Add your **SSH public key** (or let it generate one and download it).
   - Leave networking default (a public IPv4 is assigned).
3. Copy the instance's **public IP address**.

## 2. Connect and install (a few copy-paste commands)
SSH in from your Mac (user is `ubuntu` on Ubuntu images):
```bash
ssh ubuntu@YOUR_VM_IP
```
Create the secrets file, then run the installer:
```bash
sudo mkdir -p /opt/cinema-bot && sudo chown $USER /opt/cinema-bot
nano /opt/cinema-bot/.env          # paste the two lines you were given, save
curl -fsSL https://raw.githubusercontent.com/peremiller/cinema-bot/main/deploy/setup.sh | bash
```
That installs Python + deps, sets the timezone to Asia/Manila, and registers a
**systemd service** so the bot starts on boot and restarts if it ever crashes.

## 3. Stop the laptop copy (so only one instance polls the token)
On your **Mac** (two bots on one token cause `409 Conflict`):
```bash
launchctl unload ~/Library/LaunchAgents/com.cinemabot.plist
```

## Operating it
```bash
journalctl -u cinema-bot -f          # live logs
sudo systemctl restart cinema-bot    # restart
sudo systemctl status cinema-bot     # health
```
To update after code changes: re-run the `curl ... | bash` line (it pulls latest
and restarts).

## Notes
- User data (saved locations, daily subscriptions, mall-distance cache) lives in
  `/opt/cinema-bot/data/` on the VM's persistent disk — it survives reboots and
  updates.
- `.env` stays only on the VM; it is never committed to GitHub.
