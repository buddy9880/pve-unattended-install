#!/bin/bash
set -euo pipefail

keys_url="https://github.com/buddy9880.keys"
authorized_keys="/etc/pve/priv/authorized_keys"
tmp_keys="$(mktemp)"

cleanup() {
  rm -f "$tmp_keys"
}
trap cleanup EXIT

curl \
  --fail \
  --silent \
  --show-error \
  --location \
  --connect-timeout 10 \
  --max-time 60 \
  --retry 8 \
  --retry-delay 5 \
  --retry-max-time 180 \
  --retry-all-errors \
  "$keys_url" \
  -o "$tmp_keys"

touch "$authorized_keys"
chmod 600 "$authorized_keys"

while IFS= read -r key; do
  test -n "$key" || continue
  grep -qxF "$key" "$authorized_keys" || printf '%s\n' "$key" >> "$authorized_keys"
done < "$tmp_keys"
