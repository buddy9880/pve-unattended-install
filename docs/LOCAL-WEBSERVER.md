# Local Python Webserver Guide

This guide is for the simple local webserver in
`answer_server/webserver/webserver.py`.

Use this option when you want to serve one local answer file from your laptop,
desktop, or another machine on the same network as the Proxmox installer.

Command examples in this guide are indented so they are safe to copy from either
the rendered page or the raw file. Copy the indented command lines only; labels
such as `Bash:` and `PowerShell:` are not commands.

## What This Does

The local webserver:

- runs on port `8080`
- serves one answer file that you choose when it starts
- can also serve `answer_server/firstboot.sh`
- responds to the `POST` request Proxmox sends during unattended install

This is the simplest setup, but the webserver must stay running while Proxmox is
installing.

## Prerequisites

Install these first:

- Python 3
- `proxmox-auto-install-assistant`
- a machine on the same network as the Proxmox installer

Make sure these files are in the repo folder:

- `answer_server/webserver/webserver.py`
- `answer_server/firstboot.sh`, if your answer file uses it
- `vars/pve-temp.toml` or `vars/pve-main.toml`

## Start the Webserver

From the repo folder, run:

PowerShell:

    python .\answer_server\webserver\webserver.py


Bash:

    python3 ./answer_server/webserver/webserver.py


When prompted, enter the answer file for the node you are installing:

    vars/pve-temp.toml


The server listens on:

    http://0.0.0.0:8080/


From another machine, use the actual IP address of the machine running the
server, for example:

    http://192.168.1.50:8080/


## Test It

Open a second terminal.

PowerShell:

    Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/answers"
    
    $body = @{ product = "pve"; hostname = "test-node" } | ConvertTo-Json
    Invoke-RestMethod `
      -Method Post `
      -Uri "http://127.0.0.1:8080/answer" `
      -ContentType "application/json" `
      -Body $body


Bash:

    curl http://127.0.0.1:8080/answers
    
    curl -X POST http://127.0.0.1:8080/answer \
      -H 'content-type: application/json' \
      --data '{"product":"pve","hostname":"test-node"}'


You should see the TOML answer file.

If `firstboot.sh` is present, test it too:

PowerShell:

    Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/firstboot.sh"


Bash:

    curl http://127.0.0.1:8080/firstboot.sh


## Prepare the Proxmox ISO

Use the IP address of the machine running
`answer_server/webserver/webserver.py`.

PowerShell:

    proxmox-auto-install-assistant prepare-iso .\ `
      --fetch-from http `
      --url "http://192.168.1.50:8080/answer"


Bash:

    proxmox-auto-install-assistant prepare-iso ./ \
      --fetch-from http \
      --url "http://192.168.1.50:8080/answer"


Replace `192.168.1.50` with your machine's IP address.

## First Boot Script URL

If your answer file references `firstboot.sh`, use this URL format:

    http://192.168.1.50:8080/firstboot.sh


Replace `192.168.1.50` with your machine's IP address.

## Common Problems

If Proxmox cannot reach the answer file:

- confirm the webserver is still running
- confirm both machines are on the same network
- check your firewall allows inbound TCP port `8080`
- test from another machine with `curl http://192.168.1.50:8080/answers`

If the server says the answer file was not found:

- run the command from the repo folder
- enter a real answer file path such as `vars/pve-temp.toml` when prompted
- confirm the answer file exists in `vars/`

If `firstboot.sh` returns `404`:

- confirm `answer_server/firstboot.sh` exists
- confirm the URL ends with `/firstboot.sh`
