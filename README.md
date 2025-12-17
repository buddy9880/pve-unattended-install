# Proxmox Unattended Install

Automated Proxmox VE installation using answer files and a local webserver.

# Files
- **pve-temp.toml** - Answer file with network, disk, and system configuration
- **firstboot.sh** - Script that installs SSH keys from GitHub on first boot
- **webserver.py** - HTTP server that serves both files during installation

# Create the ISO with the hostname or ip address (WSL)
proxmox-auto-install-assistant prepare-iso /path/to/proxmox.iso \
  --fetch-from http \
  --url "http://buddy-laptop.local:8080/"

# Start the webserver from directory where files are saved, outside of WSL
py ./webserver.py

# The webserver serves HTTP POST and GET
http://buddy-laptop.local:8080/
http://buddy-laptop.local:8080/firstboot.sh

# The firstboot script can also be fetched from github
https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/firstboot.sh
Edit `firstboot.sh` to change SSH key source (default: `https://github.com/buddy9880.keys`)

# Notes
- The webserver must be running during Proxmox installation
- SSH keys are fetched from GitHub and installed automatically on first boot
- The answer file configures: network, disk, timezone, keyboard, and first boot script
