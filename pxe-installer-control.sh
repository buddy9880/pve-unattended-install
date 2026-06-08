#!/bin/sh
set -eu

ARMED_FILE="/var/www/html/pxe/proxmox/ARMED"
AUTO_SCRIPT="/srv/tftp/autoexec.ipxe"
ISO_FILE="/var/www/html/pxe/proxmox/proxmox-auto.iso"

status() {
  if [ -e "$ARMED_FILE" ]; then
    echo "PXE installer: ARMED"
  else
    echo "PXE installer: disarmed"
  fi

  if [ -f "$AUTO_SCRIPT" ]; then
    echo "autoexec.ipxe: present"
  else
    echo "autoexec.ipxe: missing"
  fi

  if [ -f "$ISO_FILE" ]; then
    iso_size="$(du -h "$ISO_FILE" | awk '{print $1}')"
    echo "Proxmox ISO: present ($iso_size)"
  else
    echo "Proxmox ISO: missing"
  fi
}

arm() {
  sudo touch "$ARMED_FILE"
  sudo chmod 0644 "$ARMED_FILE"
  echo "PXE installer armed."
}

disarm() {
  sudo rm -f "$ARMED_FILE"
  echo "PXE installer disarmed."
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [status|arm|disarm]

Without arguments, shows status and prompts for an action.
EOF
}

interactive() {
  status
  echo
  printf "Choose action: [a]rm, [d]isarm, [s]tatus, [q]uit: "
  read -r choice

  case "$choice" in
    a|A|arm) arm ;;
    d|D|disarm) disarm ;;
    s|S|status) status ;;
    q|Q|quit|"") exit 0 ;;
    *) echo "Unknown choice: $choice" >&2; exit 2 ;;
  esac
}

case "${1:-}" in
  "") interactive ;;
  status) status ;;
  arm) arm ;;
  disarm) disarm ;;
  -h|--help|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
