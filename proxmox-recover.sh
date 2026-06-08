#!/bin/sh
set -eu

MESHCMD="${MESHCMD:-/home/buddy/bin/meshcmd}"
PXE_CONTROL="${PXE_CONTROL:-/home/buddy/pxe-installer-control.sh}"
CONFIG_DIR="${CONFIG_DIR:-/home/buddy/.config/proxmox-recover}"
NODES_FILE="${NODES_FILE:-$CONFIG_DIR/nodes.conf}"
DEFAULT_WAIT_SECONDS="${DEFAULT_WAIT_SECONDS:-300}"

usage() {
  cat <<EOF
Usage:
  $(basename "$0") status
  $(basename "$0") scan [cidr]
  $(basename "$0") recover <node> [wait-seconds]

Config:
  $NODES_FILE

nodes.conf format:
  node_name amt_host amt_user password_file tls

Example:
  pve-temp 192.168.1.47 admin /home/buddy/.config/proxmox-recover/amt-password no
  pve-main 192.168.1.200 admin /home/buddy/.config/proxmox-recover/amt-password no
EOF
}

die() {
  echo "error: $*" >&2
  exit 1
}

require_file() {
  [ -f "$1" ] || die "missing file: $1"
}

status() {
  echo "MeshCmd: $MESHCMD"
  if [ -x "$MESHCMD" ]; then
    "$MESHCMD" 2>&1 | sed -n '1p'
  else
    echo "MeshCmd executable is missing"
  fi

  echo
  "$PXE_CONTROL" status

  echo
  if [ -f "$NODES_FILE" ]; then
    echo "Configured nodes:"
    awk '
      /^[[:space:]]*($|#)/ { next }
      { printf "  %s -> %s (%s, tls=%s)\n", $1, $2, $3, $5 }
    ' "$NODES_FILE"
  else
    echo "No nodes file found: $NODES_FILE"
  fi
}

scan() {
  cidr="${1:-192.168.1.0/24}"
  require_file "$MESHCMD"
  "$MESHCMD" amtscan --scan "$cidr"
}

lookup_node() {
  node="$1"
  require_file "$NODES_FILE"

  awk -v node="$node" '
    /^[[:space:]]*($|#)/ { next }
    $1 == node { print; found = 1; exit }
    END { if (!found) exit 1 }
  ' "$NODES_FILE"
}

recover() {
  node="$1"
  wait_seconds="${2:-$DEFAULT_WAIT_SECONDS}"

  require_file "$MESHCMD"
  require_file "$PXE_CONTROL"

  node_line="$(lookup_node "$node")" || die "node not found in $NODES_FILE: $node"
  set -- $node_line
  node_name="$1"
  amt_host="$2"
  amt_user="$3"
  password_file="$4"
  tls="${5:-no}"

  require_file "$password_file"
  amt_pass="$(tr -d '\r\n' < "$password_file")"
  [ -n "$amt_pass" ] || die "empty AMT password file: $password_file"

  tls_arg=""
  case "$tls" in
    yes|true|1|tls) tls_arg="--tls" ;;
    no|false|0|plain|"") tls_arg="" ;;
    *) die "invalid tls value for $node_name: $tls" ;;
  esac

  echo "Target: $node_name ($amt_host)"
  echo "Arming PXE installer..."
  "$PXE_CONTROL" arm

  disarm_on_exit() {
    echo "Disarming PXE installer..."
    "$PXE_CONTROL" disarm || true
  }
  trap disarm_on_exit EXIT INT TERM

  echo "Requesting AMT reset to PXE..."
  "$MESHCMD" amtpower \
    --reset \
    --bootdevice pxe \
    --host "$amt_host" \
    --user "$amt_user" \
    --pass "$amt_pass" \
    $tls_arg

  echo "Waiting ${wait_seconds}s before disarming..."
  sleep "$wait_seconds"
}

case "${1:-}" in
  status) status ;;
  scan) scan "${2:-}" ;;
  recover)
    [ $# -ge 2 ] || { usage >&2; exit 2; }
    recover "$2" "${3:-$DEFAULT_WAIT_SECONDS}"
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
