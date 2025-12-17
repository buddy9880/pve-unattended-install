# Raspberry Pi Setup Guide

Complete setup instructions for running the Proxmox unattended install webserver on a Raspberry Pi Zero 2 W.

## Prerequisites

- Raspberry Pi Zero 2 W (or any Pi with network connectivity)
- Raspberry Pi OS installed and configured
- Static IP address: `192.168.1.253`
- Internet connection (to fetch files from GitHub)
- SSH access to the Pi

## Quick Start

```bash
# 1. Create directory for the webserver
mkdir -p ~/proxmox-server
cd ~/proxmox-server

# 2. Download the webserver script
wget https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/pi-webserver.py

# 3. Make it executable
chmod +x pi-webserver.py

# 4. Test the webserver
python3 pi-webserver.py
```

The webserver should start and display:
```
======================================================================
Raspberry Pi Proxmox Webserver Started
======================================================================
Listening on: http://0.0.0.0:8080/
GitHub Repo:  buddy9880/pve-unattended-install
Branch:       main

Endpoints:
  POST /answer    → Fetches answer.toml from GitHub
  GET  /answer    → Fetches answer.toml from GitHub
  GET  /firstboot → Fetches firstboot.sh from GitHub

Note: Files are fetched from GitHub on EVERY request (no caching)
======================================================================
```

## Testing

From your laptop or another machine on the network:

```bash
# Test answer file endpoint
curl http://192.168.1.253:8080/answer

# Test firstboot script endpoint
curl http://192.168.1.253:8080/firstboot

# Test POST request (what Proxmox uses)
curl -X POST http://192.168.1.253:8080/answer
```

If you see the file contents, it's working!

## Setting Up Systemd Service (Auto-start on Boot)

### Step 1: Download the service file

```bash
cd ~/proxmox-server
wget https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/proxmox-webserver.service
```

### Step 2: Install the service

```bash
# Copy service file to systemd directory
sudo cp proxmox-webserver.service /etc/systemd/system/

# Reload systemd to recognize the new service
sudo systemctl daemon-reload

# Enable the service to start on boot
sudo systemctl enable proxmox-webserver.service

# Start the service now
sudo systemctl start proxmox-webserver.service
```

### Step 3: Verify the service is running

```bash
# Check service status
sudo systemctl status proxmox-webserver.service

# View logs
sudo journalctl -u proxmox-webserver.service -f
```

You should see output indicating the service is active and running.

## Managing the Service

```bash
# Start the service
sudo systemctl start proxmox-webserver.service

# Stop the service
sudo systemctl stop proxmox-webserver.service

# Restart the service
sudo systemctl restart proxmox-webserver.service

# Check service status
sudo systemctl status proxmox-webserver.service

# View live logs
sudo journalctl -u proxmox-webserver.service -f

# View last 50 log lines
sudo journalctl -u proxmox-webserver.service -n 50

# Disable auto-start on boot
sudo systemctl disable proxmox-webserver.service
```

## Setting Static IP Address

If your Pi doesn't already have a static IP, configure it:

### Using nmcli (Network Manager):

```bash
# List connections
nmcli connection show

# Set static IP (replace "Wired connection 1" with your connection name)
sudo nmcli connection modify "Wired connection 1" \
  ipv4.addresses 192.168.1.253/24 \
  ipv4.gateway 192.168.1.254 \
  ipv4.dns "1.1.1.1" \
  ipv4.method manual

# Restart connection
sudo nmcli connection down "Wired connection 1"
sudo nmcli connection up "Wired connection 1"
```

### Using dhcpcd (older method):

```bash
# Edit dhcpcd configuration
sudo nano /etc/dhcpcd.conf

# Add these lines at the end:
interface eth0
static ip_address=192.168.1.253/24
static routers=192.168.1.254
static domain_name_servers=1.1.1.1

# Save and restart networking
sudo systemctl restart dhcpcd
```

## Creating the Proxmox ISO

Once the Pi webserver is running, create your Proxmox installation ISO:

```bash
# On your laptop/WSL
proxmox-auto-install-assistant prepare-iso /path/to/proxmox.iso \
  --fetch-from http \
  --url "http://192.168.1.253:8080/answer"
```

Note: The URL ends in `/answer` (not `/` or `/answer.toml`)

## How It Works

1. **Proxmox boots** from the prepared ISO
2. **Sends POST request** to `http://192.168.1.253:8080/answer`
3. **Pi webserver receives request** and fetches latest `answer.toml` from GitHub
4. **Pi serves answer file** to Proxmox
5. **Proxmox reads config** and sees firstboot URL: `http://192.168.1.253:8080/firstboot`
6. **Proxmox requests firstboot script** via GET request
7. **Pi fetches and serves** `firstboot.sh` from GitHub
8. **Installation completes** and firstboot script runs

## Troubleshooting

### Service won't start

```bash
# Check for errors
sudo journalctl -u proxmox-webserver.service -n 50

# Check if port 8080 is already in use
sudo netstat -tlnp | grep 8080

# Try running manually to see errors
cd ~/proxmox-server
python3 pi-webserver.py
```

### Can't connect to webserver from other machines

```bash
# Check firewall (if using UFW)
sudo ufw status
sudo ufw allow 8080/tcp

# Check if service is listening on all interfaces
sudo netstat -tlnp | grep 8080
# Should show: 0.0.0.0:8080 (not 127.0.0.1:8080)

# Test locally on Pi
curl http://localhost:8080/answer
```

### GitHub fetch fails

```bash
# Test internet connectivity from Pi
curl -I https://github.com

# Test raw GitHub URL directly
curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/answer.toml

# Check DNS resolution
nslookup raw.githubusercontent.com
```

### Files not updating from GitHub

The webserver fetches files on **every request** (no caching). If you push changes to GitHub:

1. Changes should be visible immediately on next request
2. No need to restart the service
3. Test with: `curl http://192.168.1.253:8080/answer`

If files still aren't updating:
- Verify changes are pushed to GitHub: https://github.com/buddy9880/pve-unattended-install
- Check GitHub is returning the updated file: `curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/answer.toml`
- Clear your browser cache if testing in a browser

## Updating the Webserver

If you need to update `pi-webserver.py`:

```bash
cd ~/proxmox-server

# Backup current version
cp pi-webserver.py pi-webserver.py.backup

# Download latest version
wget -O pi-webserver.py https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/pi-webserver.py

# Restart the service
sudo systemctl restart proxmox-webserver.service
```

## Security Considerations

Current setup:
- Webserver runs as `pi` user (not root)
- No authentication on webserver
- Files served from public GitHub repo
- Answer file contains password hash (readable by anyone on network)

For production use, consider:
- Adding basic authentication to the webserver
- Using a private GitHub repo (requires GitHub token)
- Restricting firewall to only allow connections from specific IPs
- Using HTTPS with a reverse proxy (nginx, caddy, etc.)

## File Locations

```
/home/pi/proxmox-server/
├── pi-webserver.py              # Main webserver script
└── proxmox-webserver.service    # Systemd service file (optional)

/etc/systemd/system/
└── proxmox-webserver.service    # Installed service file
```

## Useful Commands

```bash
# Watch logs in real-time
sudo journalctl -u proxmox-webserver.service -f

# Check Pi's IP address
ip addr show

# Check service is auto-starting on boot
sudo systemctl is-enabled proxmox-webserver.service

# Test endpoints from Pi itself
curl http://localhost:8080/answer
curl http://localhost:8080/firstboot

# Check what files are on GitHub
curl -I https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/answer.toml
curl -I https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/firstboot.sh
```

## Support

If you encounter issues:
1. Check service logs: `sudo journalctl -u proxmox-webserver.service -n 100`
2. Test GitHub connectivity: `curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/answer.toml`
3. Test local connectivity: `curl http://localhost:8080/answer`
4. Test remote connectivity: `curl http://192.168.1.253:8080/answer` (from another machine)
5. Verify static IP: `ip addr show`
