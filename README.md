# Proxmox Unattended Install

Automated Proxmox VE installation using answer files and a local webserver.  This 
was created for my own personal setup.  I couldn't just have the proxmox fetch the
answer file directly from github as github does not support HTTP POST.  The pi-webserver 
script creates a webserver on a raspberry pi that pull the latest files from github and responds
to the HTTP POST request from proxmox.

# Files
- **pve-temp.toml** - Answer file for my test environment
- **answer.toml** - Answer file fetched from the pi webserver
- **firstboot.sh** - Script that installs SSH keys from GitHub on first boot
- **webserver.py** - HTTP server that serves files from its current directory
- **pi-webserver.py** -HTTP server that fetches files from github and serves them
- **proxmox-webserver.service** - systemd service file

# Create the ISO with the hostname or ip address (WSL)
proxmox-auto-install-assistant prepare-iso /mnt/c/Users/buddy/Downloads/ --fetch-from http --url "http://<server_ip>:8080/answer"

# Start the webserver from directory where files are saved
py ./webserver.py

# The webserver serves HTTP POST and GET
http://<server_ip>:8080/answer
http://<server_ip>:8080/firstboot

# The firstboot script can also be fetched from github
https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/firstboot.sh
Edit `firstboot.sh` to change SSH key source (default: `https://github.com/buddy9880.keys`)

# Notes
- The webserver must be running during Proxmox installation
- SSH keys are fetched from GitHub and installed automatically on first boot
- The answer file configures: network, disk, timezone, keyboard, and first boot script
