#!/bin/sh
set -eu

REPO_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
WORKER_DIR="$REPO_ROOT/answer_server/cloudflare_worker"
NODE_FILE="${NODE_FILE:-$REPO_ROOT/vars/pve-node.yml}"
WORKER_URL="${WORKER_URL:-https://pve-answer.bdev.uk}"
BRANCH="${BRANCH:-$(git -C "$REPO_ROOT" branch --show-current)}"

die() {
  echo "error: $*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: $(basename "$0")

Deploys the Cloudflare Worker and tests every MAC address in:
  $NODE_FILE

Optional environment variables:
  BRANCH       Git branch to use for GitHub raw files. Default: current branch.
  WORKER_URL   Deployed Worker URL. Default: $WORKER_URL
  NODE_FILE    Node map file. Default: $NODE_FILE

Run from anywhere inside this repo:
  ./scripts/update-answer-worker.sh
EOF
}

github_raw_base_url() {
  remote_url="$(git -C "$REPO_ROOT" config --get remote.origin.url)"

  case "$remote_url" in
    git@github.com:*.git)
      repo_path="${remote_url#git@github.com:}"
      repo_path="${repo_path%.git}"
      ;;
    https://github.com/*.git)
      repo_path="${remote_url#https://github.com/}"
      repo_path="${repo_path%.git}"
      ;;
    https://github.com/*)
      repo_path="${remote_url#https://github.com/}"
      ;;
    *)
      die "could not derive GitHub repo from remote.origin.url: $remote_url"
      ;;
  esac

  printf 'https://raw.githubusercontent.com/%s/%s\n' "$repo_path" "$BRANCH"
}

update_worker_config() {
  raw_base_url="$1"

  node --input-type=module - "$WORKER_DIR/wrangler.jsonc" "$raw_base_url" <<'EOF'
import fs from "node:fs";

const [configPath, rawBaseUrl] = process.argv.slice(2);
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
config.vars = config.vars || {};
config.vars.GITHUB_RAW_BASE_URL = rawBaseUrl;
fs.writeFileSync(configPath, `${JSON.stringify(config, null, 2)}\n`);
EOF
}

list_nodes() {
  awk '
    /^[[:space:]]*[A-Za-z0-9_-]+:[[:space:]]*$/ {
      line = $0
      gsub(/^[[:space:]]+|:[[:space:]]*$/, "", line)
      if (line != "nodes") {
        node = line
      }
      next
    }
    /^[[:space:]]*mac_address:[[:space:]]*/ {
      mac = $0
      sub(/^[[:space:]]*mac_address:[[:space:]]*/, "", mac)
      gsub(/["'\''[:space:]]/, "", mac)
      if (node != "" && mac != "") {
        print node, mac
      }
    }
  ' "$NODE_FILE"
}

test_node() {
  node_name="$1"
  mac="$2"
  expected_fqdn="$node_name.local"

  body="$(curl -fsS -X POST "$WORKER_URL/answer" \
    -H 'content-type: application/json' \
    --data "{\"network_interfaces\":[{\"link\":\"eno1\",\"mac\":\"$mac\"}]}")"

  printf '%s\n' "$body" | grep -F "fqdn = \"$expected_fqdn\"" >/dev/null ||
    die "$node_name ($mac) did not return expected fqdn $expected_fqdn"

  echo "PASS: $node_name ($mac) returned $expected_fqdn"
}

case "${1:-}" in
  -h|--help|help)
    usage
    exit 0
    ;;
  "")
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

[ -n "$BRANCH" ] || die "could not determine current git branch"
[ -f "$NODE_FILE" ] || die "missing node file: $NODE_FILE"
[ -d "$WORKER_DIR" ] || die "missing worker directory: $WORKER_DIR"

raw_base_url="$(github_raw_base_url)"

echo "Updating Worker GitHub raw base URL:"
echo "  $raw_base_url"
update_worker_config "$raw_base_url"

echo
echo "Deploying Worker..."
(
  cd "$WORKER_DIR"
  npm run deploy
)

echo
echo "Testing deployed Worker:"
nodes="$(list_nodes)"
[ -n "$nodes" ] || die "no nodes with mac_address found in $NODE_FILE"

printf '%s\n' "$nodes" | while read -r node_name mac; do
  test_node "$node_name" "$mac"
done
