# Proxmox VE Unattended Install

This repo contains my Proxmox VE unattended install setup. It gives the Proxmox
installer an answer file so installs can run without typing through the normal
setup screens.

This was created for my own personal setup. Proxmox fetches the answer file with
an HTTP `POST` request, and GitHub raw URLs are meant for normal `GET` requests.
This repo contains three ways to respond to the Proxmox `POST` request and serve
the answer file.

The current recommended setup is the Cloudflare Worker:

- each node has its own answer file, such as `vars/pve-temp.toml` and
  `vars/pve-main.toml`
- `vars/pve_node.txt` maps node MAC addresses to node names
- the Worker fetches those public files from GitHub raw URLs
- Proxmox downloads its answer file from the Worker at `/answer`
- the Worker chooses the right answer file from the machine information Proxmox
  sends in the `POST` body
- the default `workers.dev` URL and preview URLs are disabled, so the intended
  production URL is the custom domain `https://pve-answer.bdev.uk`

There are also two local network options:

- [Local Python webserver](docs/LOCAL-WEBSERVER.md) - run `webserver.py` from a
  laptop, desktop, or temporary machine on the same network
- [Raspberry Pi GitHub webserver](docs/PI-GITHUB-WEBSERVER.md) - run
  `pi-webserver.py` on a small always-on Pi that fetches files from GitHub
- [PXE recovery boot](docs/PXE-RECOVERY.md) - boot the prepared installer over
  the network instead of using a physical USB drive

This GitHub-backed setup only makes sense if the answer files are public-safe.
Hostnames and private LAN IPs are usually low risk, but the current answer files
also include `root-password-hashed`. A password hash is not the plain password,
but it should still be treated as sensitive because someone can copy it and try
to crack it offline.

## Normal Cloudflare Workflow

When coming back to this later, the usual order is:

1. Install or activate Node.js 22.
2. Update `vars/pve_node.txt` if a node MAC address changes.
3. Update the local node answer files, such as `vars/pve-temp.toml` and
   `vars/pve-main.toml`.
4. Commit and push the `vars/` changes to GitHub.
5. Run `npm install` from `answer_server/cloudflare_worker/` if dependencies are
   missing.
6. Run `npm run deploy` from `answer_server/cloudflare_worker/`.
7. Test `https://pve-answer.bdev.uk/answer`.
8. Download the Proxmox ISO and run `proxmox-auto-install-assistant prepare-iso`.

## Copy/Paste Note

Command examples in this README are indented instead of wrapped in Markdown
code fences. That keeps the commands safe to copy from either the rendered
README or the raw file. Copy the indented command lines only; labels such as
`Bash:` and `PowerShell:` are just labels.

## What Is Included

- `answer_server/cloudflare_worker/src/worker.js` - the Cloudflare Worker
- `answer_server/cloudflare_worker/wrangler.jsonc` - Worker settings
- `answer_server/cloudflare_worker/package.json` - install and deploy commands
- `vars/pve_node.txt` - node name, MAC address, and IP address map
- `vars/pve-temp.toml` - answer file for `pve-temp`
- `vars/pve-main.toml` - answer file for `pve-main`
- `vars/example_answer.toml` - safe example answer file
- `answer_server/firstboot.sh` - optional first boot script
- `answer_server/webserver/webserver.py` - simple local network webserver
- `answer_server/webserver/pi-webserver.py` - Raspberry Pi webserver that fetches
  files from GitHub
- `docs/` - setup guides for the non-Cloudflare options

Do not commit these local secret files:

- `answer-token.txt`
- `.dev.vars`
- `.env`

They are ignored by Git.

## Worker URLs

The Worker has these paths:

- `GET /health` checks that the Worker is running
- `GET /nodes` returns the GitHub node map the Worker is using
- `POST /answer` returns the answer file for the requesting machine

Everything else returns an error. `/answer` must be a `POST` request because that
is how the Proxmox auto install flow fetches the answer file.

The examples below use:

    https://pve-answer.bdev.uk


If you use a different custom domain, replace `pve-answer.bdev.uk` in the
commands.

## Prerequisites

Install these first:

- Node.js 22
- npm, which comes with Node.js
- a Cloudflare account

You do not need to install Wrangler globally. This repo installs Wrangler locally
with `npm install`.

## Install Node 22

Wrangler needs a recent Node.js version. This repo uses Node.js 22.

On Linux, macOS, or WSL, the easiest option is `nvm`:

    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
    source ~/.nvm/nvm.sh
    nvm install 22
    nvm use 22
    node --version
    npm --version


If you already have `nvm` installed, you only need:

    source ~/.nvm/nvm.sh
    nvm install 22
    nvm use 22


On Windows PowerShell, use one of these options:

- install Node.js 22 from the Node.js website
- install `nvm-windows`, then run:

    nvm install 22
    nvm use 22
    node --version
    npm --version


## Install and Login

Run these commands from the Worker folder.

PowerShell:

    cd .\answer_server\cloudflare_worker
    npm install
    npx wrangler login


Bash:

    cd /home/buddy/proxmox-recovery-kit/answer_server/cloudflare_worker
    source ~/.nvm/nvm.sh
    nvm use 22
    npm install
    npx wrangler login


`npx wrangler login` opens a browser so you can connect this project to your
Cloudflare account.

If you use `nvm`, run `source ~/.nvm/nvm.sh` and `nvm use 22` in each new
terminal before running `npm` or `npx wrangler` commands.

## Test Locally

The local Worker fetches files from the GitHub raw URL configured in
`answer_server/cloudflare_worker/wrangler.jsonc`. Push `vars/pve_node.txt` and
the `vars/*.toml` files before testing if you want the deployed GitHub copy to
match your local copy.

Start the local Worker:

PowerShell:

    cd .\answer_server\cloudflare_worker
    npm run dev


Bash:

    cd /home/buddy/proxmox-recovery-kit/answer_server/cloudflare_worker
    npm run dev


Open a second terminal and test it.

PowerShell:

    Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8787/health"
    
    $body = @{ network_interfaces = @(@{ link = "eno1"; mac = "10:62:E5:00:17:8D" }) } | ConvertTo-Json -Depth 4
    Invoke-RestMethod `
      -Method Post `
      -Uri "http://127.0.0.1:8787/answer" `
      -ContentType "application/json" `
      -Body $body


Bash:

    curl http://127.0.0.1:8787/health
    curl http://127.0.0.1:8787/nodes
    
    curl -X POST "http://127.0.0.1:8787/answer" \
      -H 'content-type: application/json' \
      --data '{"network_interfaces":[{"link":"eno1","mac":"10:62:E5:00:17:8D"}]}'


You should see `ok` from `/health`, and TOML text from `/answer`.

To confirm `/answer` still rejects normal browser-style `GET` requests:

    curl -i "http://127.0.0.1:8787/answer"


Expected result: status `405`.

## Update Answer Files

Edit the local answer file for the node you want to change:

- `vars/pve-temp.toml` for `pve-temp`
- `vars/pve-main.toml` for `pve-main`

If a machine's MAC address changes, update `vars/pve_node.txt` too.

After changing files under `vars/`, commit and push them to GitHub. The Worker
fetches from GitHub on request, so answer-file-only changes do not require a
Worker deploy.

## Check GitHub Raw Files

Before deploying or preparing an ISO, confirm GitHub is serving the files the
Worker will fetch.

PowerShell:

    Invoke-RestMethod -Uri "https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve_node.txt"
    Invoke-RestMethod -Uri "https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve-temp.toml"
    Invoke-RestMethod -Uri "https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve-main.toml"


Bash:

    curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve_node.txt
    curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve-temp.toml
    curl https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/vars/pve-main.toml

## Deploy

Deploy the Worker to Cloudflare:

PowerShell:

    cd .\answer_server\cloudflare_worker
    npm run deploy


Bash:

    cd /home/buddy/proxmox-recovery-kit/answer_server/cloudflare_worker
    npm run deploy


This repo disables the default `workers.dev` URL and Cloudflare Preview URLs in
`wrangler.jsonc`. After deployment, use the custom domain:

    https://pve-answer.bdev.uk


If you create a different custom domain in Cloudflare, use that domain instead.

## Test the Deployed Worker

These commands confirm the deployed Worker is reachable and can select both node
answer files from MAC addresses.

PowerShell:

    $workerUrl = "https://pve-answer.bdev.uk"
    
    Invoke-RestMethod -Method Get -Uri "$workerUrl/health"
    Invoke-RestMethod -Method Get -Uri "$workerUrl/nodes"
    
    $body = @{ network_interfaces = @(@{ link = "eno1"; mac = "10:62:E5:00:17:8D" }) } | ConvertTo-Json -Depth 4
    Invoke-RestMethod `
      -Method Post `
      -Uri "$workerUrl/answer" `
      -ContentType "application/json" `
      -Body $body


Bash:

    worker_url="https://pve-answer.bdev.uk"
    
    curl "$worker_url/health"
    curl "$worker_url/nodes"
    
    curl -X POST "$worker_url/answer" \
      -H 'content-type: application/json' \
      --data '{"network_interfaces":[{"link":"eno1","mac":"10:62:E5:00:17:8D"}]}'

    curl -X POST "$worker_url/answer" \
      -H 'content-type: application/json' \
      --data '{"network_interfaces":[{"link":"enp0s31f6","mac":"90:8D:6E:8C:45:CF"}]}'


To confirm `/answer` rejects normal browser-style `GET` requests:

PowerShell:

    try {
      Invoke-RestMethod -Method Get -Uri "$workerUrl/answer"
    } catch {
      $_.Exception.Response.StatusCode.value__
    }


Bash:

    curl -i "$worker_url/answer"


Expected result: status `405`.

To confirm unknown machines are refused:

PowerShell:

    $unknownBody = @{ network_interfaces = @(@{ link = "eno1"; mac = "00:11:22:33:44:55" }) } | ConvertTo-Json -Depth 4
    try {
      Invoke-RestMethod `
        -Method Post `
        -Uri "$workerUrl/answer" `
        -ContentType "application/json" `
        -Body $unknownBody
    } catch {
      $_.Exception.Response.StatusCode.value__
    }


Bash:

    curl -i -X POST "$worker_url/answer" \
      -H 'content-type: application/json' \
      --data '{"network_interfaces":[{"link":"eno1","mac":"00:11:22:33:44:55"}]}'


Expected result: status `404`.

## Use It When Preparing the Proxmox ISO

Download the Proxmox VE ISO first.

Bash:

    wget https://enterprise.proxmox.com/iso/proxmox-ve_9.2-1.iso


PowerShell:

    Invoke-WebRequest `
      -Uri "https://enterprise.proxmox.com/iso/proxmox-ve_9.2-1.iso" `
      -OutFile ".\proxmox-ve_9.2-1.iso"


Then use the deployed `/answer` URL with `proxmox-auto-install-assistant`.

PowerShell:

    proxmox-auto-install-assistant prepare-iso .\proxmox-ve_9.2-1.iso `
      --fetch-from http `
      --url "https://pve-answer.bdev.uk/answer"


Bash:

    proxmox-auto-install-assistant prepare-iso ./proxmox-ve_9.2-1.iso \
      --fetch-from http \
      --url "https://pve-answer.bdev.uk/answer"


If your answer file references `firstboot.sh`, you can keep using the public
GitHub raw URL:

    https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/answer_server/firstboot.sh


## Custom Domain and Default URLs

This repo is set up to use a custom domain and keep the extra Cloudflare URLs
off. In `wrangler.jsonc`:

- `workers_dev` is `false`
- `preview_urls` is `false`

The custom domain is managed in the Cloudflare dashboard:

1. Open the Cloudflare dashboard.
2. Go to Workers & Pages.
3. Select `pve-answer-worker`.
4. Open Settings, then Domains & Routes.
5. Confirm `pve-answer.bdev.uk` is listed as a custom domain.

Use the custom URL when preparing the ISO:

PowerShell:

    proxmox-auto-install-assistant prepare-iso .\proxmox-ve_9.2-1.iso `
      --fetch-from http `
      --url "https://pve-answer.bdev.uk/answer"


Bash:

    proxmox-auto-install-assistant prepare-iso ./proxmox-ve_9.2-1.iso \
      --fetch-from http \
      --url "https://pve-answer.bdev.uk/answer"
