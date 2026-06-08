# Raspberry Pi GitHub Webserver Guide

This guide is for the Raspberry Pi webserver in
`answer_server/webserver/pi-webserver.py`.

Use this option when you want a small always-on server on your network. The Pi
fetches the latest files from GitHub each time Proxmox asks for them.

Command examples in this guide are indented so they are safe to copy from either
the rendered page or the raw file. Copy the indented command lines only; labels
such as `Bash:` and `PowerShell:` are not commands.

## What This Does

The Pi webserver:

- runs on port `8080`
- serves `/nodes` from GitHub file `vars/pve_node.txt`
- serves `/answer` from GitHub file `vars/<node>.toml`, selected by MAC address
- serves `/firstboot` from GitHub file `answer_server/firstboot.sh`
- supports the `POST` request Proxmox sends during unattended install
- can run automatically on boot with `systemd`

This setup is useful if you do not want to keep your laptop running during every
install.

## Important Note About Secrets

This server fetches public files from GitHub raw URLs configured in
`pi-webserver.py`.

That means this option is best for a lab network or a public-safe answer file.
If your real answer files contain sensitive values, do not use this public
GitHub setup.

## Prerequisites

You need:

- a Raspberry Pi or similar Linux machine
- Python 3
- internet access from the Pi
- SSH access to the Pi
- a stable IP address for the Pi

The examples below use this Pi IP address:

    192.168.1.253


Replace it with your Pi's real IP address.

## Install the Webserver

SSH into the Pi, then run:

    mkdir -p ~/proxmox-server
    cd ~/proxmox-server
    
    wget https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/answer_server/webserver/pi-webserver.py
    chmod +x pi-webserver.py


Start it manually for a quick test:

    python3 ./pi-webserver.py


You should see the server start on port `8080`.

## Test It

From another machine on the same network:

    curl http://192.168.1.253:8080/nodes
    curl "http://192.168.1.253:8080/answer?node=pve-temp"
    curl http://192.168.1.253:8080/firstboot
    
    curl -X POST http://192.168.1.253:8080/answer \
      -H 'content-type: application/json' \
      --data '{"network_interfaces":[{"link":"eno1","mac":"10:62:E5:00:17:8D"}]}'


You should see the node map, the selected answer file, and `firstboot.sh` from
GitHub.

Stop the manual server with `Ctrl+C` before setting up the service.

## Run It Automatically on Boot

Download the service file:

    cd ~/proxmox-server
    wget https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/proxmox-webserver.service


Check the service file before installing it:

    nano proxmox-webserver.service


Make sure these lines match your Pi user and folder:

    User=buddy
    WorkingDirectory=/home/buddy/proxmox-server
    ExecStart=/usr/bin/python3 /home/buddy/proxmox-server/pi-webserver.py


For the normal Raspberry Pi OS user, these lines may need to be:

    User=pi
    WorkingDirectory=/home/pi/proxmox-server
    ExecStart=/usr/bin/python3 /home/pi/proxmox-server/pi-webserver.py


Install and start the service:

    sudo cp proxmox-webserver.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable proxmox-webserver.service
    sudo systemctl start proxmox-webserver.service


Check that it is running:

    sudo systemctl status proxmox-webserver.service


View live logs:

    sudo journalctl -u proxmox-webserver.service -f


## Prepare the Proxmox ISO

Use the Pi's `/answer` URL.

PowerShell:

    proxmox-auto-install-assistant prepare-iso .\ `
      --fetch-from http `
      --url "http://192.168.1.253:8080/answer"


Bash:

    proxmox-auto-install-assistant prepare-iso ./ \
      --fetch-from http \
      --url "http://192.168.1.253:8080/answer"


Replace `192.168.1.253` with your Pi's IP address.

## First Boot Script URL

If your answer file references the Pi-hosted first boot script, use:

    http://192.168.1.253:8080/firstboot


## Useful Service Commands

    sudo systemctl start proxmox-webserver.service
    sudo systemctl stop proxmox-webserver.service
    sudo systemctl restart proxmox-webserver.service
    sudo systemctl status proxmox-webserver.service
    sudo journalctl -u proxmox-webserver.service -n 50


## Common Problems

If the service will not start:

    sudo journalctl -u proxmox-webserver.service -n 50


Check that the `User`, `WorkingDirectory`, and `ExecStart` lines match the actual
Pi username and folder.

If other machines cannot connect:

- confirm the Pi IP address is correct
- confirm the service is running
- check that port `8080` is not blocked by a firewall
- test locally on the Pi with `curl http://localhost:8080/answer`

If GitHub fetches fail:

    curl -I https://github.com
    curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve_node.txt
    curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve-temp.toml


If GitHub shows the wrong file contents:

- confirm your changes were pushed to GitHub
- confirm they are on the `main` branch
- test the raw GitHub URL directly
