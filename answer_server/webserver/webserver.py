#!/usr/bin/env python3
"""
Cross-platform Proxmox answer-file webserver.

This serves answer files from local files. Proxmox POSTs machine details to
/answer, including network interface MAC addresses. The server matches those
MAC addresses against vars/pve-node.yml and returns vars/<node>.toml.
"""

import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import sys
from typing import Optional
from urllib.parse import parse_qs, urlparse


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
REPO_ROOT = os.environ.get("PROXMOX_RECOVERY_ROOT", DEFAULT_REPO_ROOT)
PORT = int(os.environ.get("PORT", "8080"))
NODE_MAP_FILE = os.path.join(REPO_ROOT, "vars", "pve-node.yml")
FIRSTBOOT_FILE = os.path.join(REPO_ROOT, "scripts", "firstboot.sh")
NODE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def set_paths(repo_root: str):
    global REPO_ROOT, NODE_MAP_FILE, FIRSTBOOT_FILE

    REPO_ROOT = os.path.abspath(repo_root)
    NODE_MAP_FILE = os.path.join(REPO_ROOT, "vars", "pve-node.yml")
    FIRSTBOOT_FILE = os.path.join(REPO_ROOT, "scripts", "firstboot.sh")


def normalize_mac(mac: object) -> str:
    return mac.lower().replace("-", ":") if isinstance(mac, str) else ""


def parse_node_map(text: str) -> dict[str, str]:
    nodes = {}
    current_node = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line == "nodes:":
            continue

        node_match = re.match(r"^([A-Za-z0-9_-]+):$", line)
        if node_match:
            current_node = node_match.group(1)
            continue

        mac_match = re.match(r"^mac_address:\s*[\"']?([^\"']+)[\"']?$", line)
        if mac_match and current_node:
            mac = normalize_mac(mac_match.group(1).strip())
            if mac:
                nodes[mac] = current_node

    return nodes


def select_node_from_post(body: bytes) -> Optional[str]:
    try:
        system_info = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return None

    interfaces = system_info.get("network_interfaces")
    if not isinstance(interfaces, list):
        return None

    node_map = parse_node_map(read_file(NODE_MAP_FILE).decode("utf-8"))
    for iface in interfaces:
        if not isinstance(iface, dict):
            continue
        node_name = node_map.get(normalize_mac(iface.get("mac")))
        if node_name:
            return node_name

    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} - {format % args}")

    def _send_file(self, data: bytes, content_type: str = "text/plain; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_request(self, body: bytes = b""):
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip("/") or "/answer"

        if path == "/nodes":
            file_path = NODE_MAP_FILE
        elif path in ["/firstboot", "/firstboot.sh"]:
            file_path = FIRSTBOOT_FILE
        elif path == "/answer":
            if self.command == "GET":
                node_name = parse_qs(parsed_url.query).get("node", [""])[0]
                if not NODE_NAME_RE.match(node_name):
                    self.send_error(400, "Use /answer?node=pve-temp for GET testing")
                    return
            else:
                node_name = select_node_from_post(body)
                if not node_name:
                    self.send_error(404, "No answer file configured for this machine")
                    return

            file_path = os.path.join(REPO_ROOT, "vars", f"{node_name}.toml")
        else:
            self.send_error(404, "Endpoint not found. Available: /nodes, /answer, /firstboot")
            return

        try:
            self._send_file(read_file(file_path))
        except FileNotFoundError:
            self.send_error(404, f"{os.path.relpath(file_path, REPO_ROOT)} not found")

    def do_GET(self):
        self._handle_request()

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        self._handle_request(body)


def main():
    global PORT

    parser = argparse.ArgumentParser(
        description="Serve local Proxmox answer files selected by machine MAC address.",
    )
    parser.add_argument(
        "--root",
        default=REPO_ROOT,
        help="Directory containing vars/pve-node.yml, vars/<node>.toml, and scripts/firstboot.sh.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=PORT,
        help="TCP port to listen on. Default: 8080.",
    )
    args = parser.parse_args()

    set_paths(args.root)
    PORT = args.port

    server = None
    try:
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        print("=" * 70)
        print("Proxmox Answer Webserver Started")
        print("=" * 70)
        print(f"Listening on: http://0.0.0.0:{PORT}/")
        print(f"Repo root:    {REPO_ROOT}")
        print()
        print("Endpoints:")
        print("  GET  /nodes                -> Serves vars/pve-node.yml")
        print("  POST /answer               -> Selects vars/<node>.toml by MAC address")
        print("  GET  /answer?node=pve-temp -> Serves one answer file for testing")
        print("  GET  /firstboot            -> Serves scripts/firstboot.sh")
        print("=" * 70)
        print()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        if server:
            server.socket.close()
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
