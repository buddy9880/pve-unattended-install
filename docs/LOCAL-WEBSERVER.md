# Local Python Webserver Guide

This guide is for the simple local webserver in `webserver.py`.

Use this option when you want to serve `answer.toml` from your laptop, desktop,
or another machine on the same network as the Proxmox installer.

## What This Does

The local webserver:

- runs on port `8080`
- serves one answer file that you choose when it starts
- can also serve `firstboot.sh` if it is in the same folder
- responds to the `POST` request Proxmox sends during unattended install

This is the simplest setup, but the webserver must stay running while Proxmox is
installing.

## Prerequisites

Install these first:

- Python 3
- `proxmox-auto-install-assistant`
- a machine on the same network as the Proxmox installer

Make sure these files are in the repo folder:

- `webserver.py`
- `answer.toml`
- `firstboot.sh`, if your answer file uses it

## Start the Webserver

From the repo folder, run:

PowerShell:

```powershell
python .\webserver.py
```

Bash:

```bash
python3 ./webserver.py
```

When prompted, enter the answer filename:

```text
answer.toml
```

The server listens on:

```text
http://0.0.0.0:8080/
```

From another machine, use the actual IP address of the machine running the
server, for example:

```text
http://192.168.1.50:8080/
```

## Test It

Open a second terminal.

PowerShell:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/answers"

$body = @{ product = "pve"; hostname = "test-node" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8080/answer" `
  -ContentType "application/json" `
  -Body $body
```

Bash:

```bash
curl http://127.0.0.1:8080/answers

curl -X POST http://127.0.0.1:8080/answer \
  -H 'content-type: application/json' \
  --data '{"product":"pve","hostname":"test-node"}'
```

You should see the TOML answer file.

If `firstboot.sh` is present, test it too:

PowerShell:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/firstboot.sh"
```

Bash:

```bash
curl http://127.0.0.1:8080/firstboot.sh
```

## Prepare the Proxmox ISO

Use the IP address of the machine running `webserver.py`.

PowerShell:

```powershell
proxmox-auto-install-assistant prepare-iso .\ `
  --fetch-from http `
  --url "http://192.168.1.50:8080/answer"
```

Bash:

```bash
proxmox-auto-install-assistant prepare-iso ./ \
  --fetch-from http \
  --url "http://192.168.1.50:8080/answer"
```

Replace `192.168.1.50` with your machine's IP address.

## First Boot Script URL

If your answer file references `firstboot.sh`, use this URL format:

```text
http://192.168.1.50:8080/firstboot.sh
```

Replace `192.168.1.50` with your machine's IP address.

## Common Problems

If Proxmox cannot reach the answer file:

- confirm the webserver is still running
- confirm both machines are on the same network
- check your firewall allows inbound TCP port `8080`
- test from another machine with `curl http://192.168.1.50:8080/answers`

If the server says the answer file was not found:

- run the command from the repo folder
- enter `answer.toml` when prompted
- confirm `answer.toml` exists in that folder

If `firstboot.sh` returns `404`:

- confirm `firstboot.sh` is in the same folder where you started the server
- confirm the URL ends with `/firstboot.sh`
