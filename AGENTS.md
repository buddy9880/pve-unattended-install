# AGENTS.md

This repo is a Proxmox recovery kit for unattended reinstall and recovery of the
home Proxmox nodes. It is incomplete and being reorganized, so prefer small,
conservative changes that keep the current recovery path working.

## Audience and Documentation Style

Write documentation for a tech-literate user who is not a developer and may not
touch this repo again for months.

- Explain what each step does before giving commands.
- Make commands easy to copy and paste.
- Prefer complete command blocks over fragments that require memory or guesswork.
- Include the directory a command should be run from.
- Avoid unexplained jargon. When a tool name is unavoidable, add a short plain
  English explanation.
- Do not assume the user remembers the project layout, Cloudflare setup, AMT,
  PXE, iPXE, or Proxmox automated install details.

Use indented command blocks in user-facing docs when matching the existing docs.
They copy cleanly from rendered Markdown and raw files.

## Project Shape

Current purpose:

- serve Proxmox automated-install answer files
- prepare a Proxmox ISO that fetches its answer file over HTTP
- support Cloudflare Worker, local webserver, and Raspberry Pi webserver answer
  delivery options
- build toward phone-triggerable recovery, where one script can arm PXE and use
  AMT to reboot a node into the installer

Current important paths:

- `README.md` - main overview and Cloudflare Worker workflow
- `docs/LOCAL-WEBSERVER.md` - local Python webserver guide
- `docs/PI-GITHUB-WEBSERVER.md` - Raspberry Pi webserver guide
- `docs/PXE-RECOVERY.md` - PXE recovery guide
- `docs/PI-PXE-IMPLEMENTATION-NOTES.txt` - rough Pi/PXE implementation notes
- `answer_server/cloudflare_worker/` - Cloudflare Worker project
- `answer_server/webserver/` - local/Pi Python webservers and service file
- `vars/pve_node.txt` - node map used by the Cloudflare Worker
- `vars/*.toml` - example and node answer files
- `answer_server/firstboot.sh` - optional first boot script
- `proxmox-recover.sh` - top-level recovery helper for status, scan, and AMT
  reboot-to-PXE workflow
- `pxe-installer-control.sh` - PXE arm/disarm/status helper intended to run on
  the PXE host
- `todo.txt` - human scratchpad, not an agent task list unless the user says to
  use it

The repo may contain old documentation that still references pre-reorg root
paths such as `src/worker.js`, `webserver.py`, or `pve-temp.toml`. When editing,
prefer the new locations under `answer_server/` unless surrounding code or docs
clearly show otherwise.

## Safety Rules

This repo can trigger destructive infrastructure behavior. Treat reinstall,
PXE arm, AMT reset, and answer-file changes carefully.

- Do not run recovery, PXE arm, PXE disarm, AMT reset, deploy, or secret-upload
  commands unless the user asked for that specific action.
- Do not expose token values, passwords, answer-file secrets, or `.dev.vars`
  contents in chat or logs.
- Do not commit real local secret files.
- Do not change node MAC addresses, disk targets, hostnames, IP addresses, or
  partitioning settings casually. These can decide which machine is reinstalled
  and which disk is erased.
- If a command could reinstall a host or reboot hardware, say exactly what host
  it targets before running it.
- Preserve the existing `.gitignore` protections for `.dev.vars`,
  `answer-token.txt`, `answer.toml`, `.env`, and local secret files.

Known local-looking secret files may exist in the working tree because this is a
personal recovery repo. Read only what is necessary, do not print their contents,
and do not include their values in generated documentation.

## Working With `todo.txt`

`todo.txt` is a human scratchpad. It is useful for understanding the intended
future direction, especially:

- one phone-triggerable recovery script
- prepare-media workflow that downloads the latest Proxmox ISO and prepares it
- answer serving by MAC address
- PXE server arm/disarm behavior
- AMT workflow to force nodes to boot PXE

Do not treat every note in `todo.txt` as an instruction to implement now. Use it
only as background unless the user explicitly asks to work from it.

## Cloudflare Worker Notes

The Worker lives in `answer_server/cloudflare_worker/`.

Run Node/Wrangler commands from that directory:

    cd /home/buddy/proxmox-recovery-kit/answer_server/cloudflare_worker
    npm install
    npm run dev

Deploy only when the user asks:

    cd /home/buddy/proxmox-recovery-kit/answer_server/cloudflare_worker
    npm run deploy

The Worker currently fetches public files from GitHub raw URLs. Its configured
base URL is `GITHUB_RAW_BASE_URL` in `wrangler.jsonc`.

The production Worker URL documented in the repo is:

    https://pve-answer.bdev.uk

Do not assume the Worker can be tested with a normal browser request to
`/answer`. Proxmox uses `POST /answer`, and the Worker chooses the answer file
from the posted machine information. The Worker reads MAC addresses from
`vars/pve_node.txt`, then serves `vars/<node>.toml` from GitHub.

## PXE and AMT Notes

The intended recovery direction is:

1. Prepare a Proxmox automated installer ISO.
2. Put the ISO on the PXE host.
3. Arm the PXE installer only when recovery is intentional.
4. Use AMT or firmware controls to one-time boot the target node from PXE.
5. Disarm PXE after the recovery boot starts.

`pxe-installer-control.sh` manages the armed marker used by the PXE/iPXE flow.
`proxmox-recover.sh` is the higher-level helper that can show status, scan AMT,
or recover a configured node.

Because these scripts can affect real machines, do not run commands like these
without explicit user direction:

    ./pxe-installer-control.sh arm
    ./proxmox-recover.sh recover pve-temp

Status commands are generally safe:

    ./proxmox-recover.sh status
    ./pxe-installer-control.sh status

## Verification

For documentation-only changes, check the rendered logic by reading the edited
file and verify no secret values were added:

    git diff -- AGENTS.md

For Cloudflare Worker changes, use commands from the Worker directory:

    cd /home/buddy/proxmox-recovery-kit/answer_server/cloudflare_worker
    npm install
    npm run dev

If tests are added later, document the exact command here and in the relevant
README section.

For shell script changes, prefer POSIX `sh` compatibility unless the script
already opts into another shell. At minimum, run:

    sh -n ./proxmox-recover.sh
    sh -n ./pxe-installer-control.sh

## Change Hygiene

- The working tree may be dirty because the repo is being reorganized. Do not
  revert user changes.
- Keep reorganizing edits separate from behavior changes when possible.
- Update documentation paths when files move.
- Keep examples consistent with the actual current layout.
- Prefer small, direct scripts over complex automation unless the user asks for
  a larger tool.
- If adding new scripts, include `usage` output and safe defaults.
- If adding commands to docs, include the full path or `cd` first.

## Future Direction

When implementing future work, bias toward the desired recovery experience:

- a single top-level script that can be run from a phone or simple SSH session
- script-based functions that can still be orchestrated by Ansible if desired
- answer-file selection by requesting node MAC address
- PXE serving that is normally disarmed and MAC-gated
- AMT flow that can force a configured node to reboot to PXE
- clear status output before any action that could reinstall or reboot a node

The main design goal is reliable emergency recovery with minimal remembered
context.
This repo is work in progress and has not been finalized.  Do not update docs unless asked to do so.
