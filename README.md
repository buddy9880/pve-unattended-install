# Proxmox VE Unattended Install

This repo contains my Proxmox VE unattended install setup. It gives the Proxmox
installer an answer file so installs can run without typing through the normal
setup screens.

This was created for my own personal setup. Proxmox fetches the answer file with
an HTTP `POST` request, and GitHub raw URLs are meant for normal `GET` requests.
This repo contains three ways to respond to the Proxmox `POST` request and serve
the answer file.

The current recommended setup is the Cloudflare Worker:

- `answer.toml` stays off GitHub
- Cloudflare stores the real answer file as a secret named `ANSWER_TOML`
- Cloudflare stores a URL token as a secret named `ANSWER_TOKEN`
- Proxmox downloads it from the Worker at `/answer?token=<your-answer-token>`
- the default `workers.dev` URL and preview URLs are disabled, so the intended
  production URL is the custom domain `https://pve-answer.bdev.uk`

There are also two local network options:

- [Local Python webserver](docs/LOCAL-WEBSERVER.md) - run `webserver.py` from a
  laptop, desktop, or temporary machine on the same network
- [Raspberry Pi GitHub webserver](docs/PI-GITHUB-WEBSERVER.md) - run
  `pi-webserver.py` on a small always-on Pi that fetches files from GitHub

You can still use GitHub raw URLs for public files such as `firstboot.sh`. Keep
private values in `answer.toml` out of Git unless you intentionally choose one
of the public-file webserver options.

## Normal Cloudflare Workflow

When coming back to this later, the usual order is:

1. Install or activate Node.js 22.
2. Run `npm install`.
3. Put your real answer file in local `answer.toml`.
4. Create or reuse local `answer-token.txt`.
5. Upload `ANSWER_TOML` and `ANSWER_TOKEN` to Cloudflare.
6. Run `npm run deploy`.
7. Test `https://pve-answer.bdev.uk/answer?token=<your-answer-token>`.
8. Download the Proxmox ISO and run `proxmox-auto-install-assistant prepare-iso`.

## What Is Included

- `src/worker.js` - the Cloudflare Worker
- `wrangler.jsonc` - Cloudflare Worker settings
- `package.json` - install and deploy commands
- `example_answer.toml` - safe example answer file
- `firstboot.sh` - optional first boot script
- `webserver.py` - simple local network webserver
- `pi-webserver.py` - Raspberry Pi webserver that fetches files from GitHub
- `docs/` - setup guides for the non-Cloudflare options

Do not commit these local secret files:

- `answer.toml`
- `answer-token.txt`
- `.dev.vars`
- `.env`

They are ignored by Git.

## Worker URLs

The Worker has these paths:

- `GET /health` checks that the Worker is running
- `POST /answer?token=<your-answer-token>` returns the answer file

Everything else returns an error. `/answer` must be a `POST` request because that
is how the Proxmox auto install flow fetches the answer file. Requests without
the correct token return `401`.

The examples below use:

```text
https://pve-answer.bdev.uk
```

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

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.nvm/nvm.sh
nvm install 22
nvm use 22
node --version
npm --version
```

If you already have `nvm` installed, you only need:

```bash
source ~/.nvm/nvm.sh
nvm install 22
nvm use 22
```

On Windows PowerShell, use one of these options:

- install Node.js 22 from the Node.js website
- install `nvm-windows`, then run:

```powershell
nvm install 22
nvm use 22
node --version
npm --version
```

## Install and Login

Run these commands from the repo folder.

PowerShell:

```powershell
npm install
npx wrangler login
```

Bash:

```bash
source ~/.nvm/nvm.sh
nvm use 22
npm install
npx wrangler login
```

`npx wrangler login` opens a browser so you can connect this project to your
Cloudflare account.

If you use `nvm`, run `source ~/.nvm/nvm.sh` and `nvm use 22` in each new
terminal before running `npm` or `npx wrangler` commands.

## Test Locally

For local testing, create a `.dev.vars` file. This gives Wrangler a local copy
of the answer file without putting secrets in Git.

To test with the safe example file:

PowerShell:

```powershell
$answer = Get-Content .\example_answer.toml -Raw
@(
  "ANSWER_TOML=$($answer | ConvertTo-Json -Compress)"
  "ANSWER_TOKEN=local-test-token"
) | Set-Content .dev.vars
```

Bash:

```bash
node -e "const fs = require('fs'); console.log('ANSWER_TOML=' + JSON.stringify(fs.readFileSync('example_answer.toml', 'utf8')) + '\nANSWER_TOKEN=local-test-token')" > .dev.vars
```

To test with your real local `answer.toml`, replace `example_answer.toml` with
`answer.toml` in the commands above.

Start the local Worker:

PowerShell:

```powershell
npm run dev
```

Bash:

```bash
npm run dev
```

Open a second terminal and test it.

PowerShell:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8787/health"

$body = @{ product = "pve"; hostname = "test-node" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8787/answer?token=local-test-token" `
  -ContentType "application/json" `
  -Body $body
```

Bash:

```bash
curl http://127.0.0.1:8787/health

curl -X POST "http://127.0.0.1:8787/answer?token=local-test-token" \
  -H 'content-type: application/json' \
  --data '{"product":"pve","hostname":"test-node"}'
```

You should see `ok` from `/health`, and TOML text from `/answer`.

To confirm the token check works, try the same `POST /answer` request without
`?token=local-test-token`. Expected result: status `401`.

## Add the Cloudflare Secrets

Before deploying, store your real `answer.toml` in Cloudflare as a secret named
`ANSWER_TOML`. Then create a local `answer-token.txt` file and store that token
in Cloudflare as `ANSWER_TOKEN`.

PowerShell:

```powershell
Get-Content .\answer.toml -Raw | npx wrangler secret put ANSWER_TOML

if (-not (Test-Path .\answer-token.txt) -or -not (Get-Content .\answer-token.txt -Raw).Trim()) {
  $answerToken = [guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N")
  Set-Content -NoNewline .\answer-token.txt $answerToken
}

(Get-Content .\answer-token.txt -Raw).Trim() | npx wrangler secret put ANSWER_TOKEN
```

Bash:

```bash
source ~/.nvm/nvm.sh
nvm use 22
npx wrangler secret put ANSWER_TOML < answer.toml

answer_token="$(tr -d '\r\n' < answer-token.txt 2>/dev/null || true)"
test -n "$answer_token" || answer_token="$(openssl rand -hex 32)"
printf '%s' "$answer_token" > answer-token.txt
tr -d '\r\n' < answer-token.txt | npx wrangler secret put ANSWER_TOKEN
```

If your shell does not pass the file content correctly, run this instead:

```bash
npx wrangler secret put ANSWER_TOML
npx wrangler secret put ANSWER_TOKEN
```

Then paste the contents of `answer.toml` for `ANSWER_TOML`, and paste the
contents of `answer-token.txt` for `ANSWER_TOKEN`.

Keep `answer-token.txt` private. You need that value in the Proxmox `--url`
value.

## Deploy

Deploy the Worker to Cloudflare:

PowerShell:

```powershell
npm run deploy
```

Bash:

```bash
npm run deploy
```

This repo disables the default `workers.dev` URL and Cloudflare Preview URLs in
`wrangler.jsonc`. After deployment, use the custom domain:

```text
https://pve-answer.bdev.uk
```

If you create a different custom domain in Cloudflare, use that domain instead.

## Test the Deployed Worker

These commands confirm the deployed Worker is reachable and that the token check
is working.

PowerShell:

```powershell
$workerUrl = "https://pve-answer.bdev.uk"
$answerToken = (Get-Content .\answer-token.txt -Raw).Trim()

Invoke-RestMethod -Method Get -Uri "$workerUrl/health"

$body = @{ product = "pve"; hostname = "test-node" } | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "$workerUrl/answer?token=$answerToken" `
  -ContentType "application/json" `
  -Body $body
```

Bash:

```bash
worker_url="https://pve-answer.bdev.uk"
answer_token="$(tr -d '\r\n' < answer-token.txt)"

curl "$worker_url/health"

curl -X POST "$worker_url/answer?token=$answer_token" \
  -H 'content-type: application/json' \
  --data '{"product":"pve","hostname":"test-node"}'
```

To confirm `/answer` rejects normal browser-style `GET` requests:

PowerShell:

```powershell
try {
  Invoke-RestMethod -Method Get -Uri "$workerUrl/answer"
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

Bash:

```bash
curl -i "$worker_url/answer"
```

Expected result: status `405`.

To confirm the token check works:

PowerShell:

```powershell
try {
  Invoke-RestMethod `
    -Method Post `
    -Uri "$workerUrl/answer" `
    -ContentType "application/json" `
    -Body $body
} catch {
  $_.Exception.Response.StatusCode.value__
}
```

Bash:

```bash
curl -i -X POST "$worker_url/answer" \
  -H 'content-type: application/json' \
  --data '{"product":"pve","hostname":"test-node"}'
```

Expected result: status `401`.

## Use It When Preparing the Proxmox ISO

Download the Proxmox VE ISO first.

Bash:

```bash
wget https://enterprise.proxmox.com/iso/proxmox-ve_9.2-1.iso
```

PowerShell:

```powershell
Invoke-WebRequest `
  -Uri "https://enterprise.proxmox.com/iso/proxmox-ve_9.2-1.iso" `
  -OutFile ".\proxmox-ve_9.2-1.iso"
```

Then use the deployed `/answer` URL with `proxmox-auto-install-assistant`.

PowerShell:

```powershell
proxmox-auto-install-assistant prepare-iso .\proxmox-ve_9.2-1.iso `
  --fetch-from http `
  --url "https://pve-answer.bdev.uk/answer?token=<your-answer-token>"
```

Bash:

```bash
proxmox-auto-install-assistant prepare-iso ./proxmox-ve_9.2-1.iso \
  --fetch-from http \
  --url "https://pve-answer.bdev.uk/answer?token=<your-answer-token>"
```

If your answer file references `firstboot.sh`, you can keep using the public
GitHub raw URL:

```text
https://raw.githubusercontent.com/buddy9880/pve-unattended-install/main/firstboot.sh
```

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

```powershell
proxmox-auto-install-assistant prepare-iso .\proxmox-ve_9.2-1.iso `
  --fetch-from http `
  --url "https://pve-answer.bdev.uk/answer?token=<your-answer-token>"
```

Bash:

```bash
proxmox-auto-install-assistant prepare-iso ./proxmox-ve_9.2-1.iso \
  --fetch-from http \
  --url "https://pve-answer.bdev.uk/answer?token=<your-answer-token>"
```
