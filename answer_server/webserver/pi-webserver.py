#!/usr/bin/env python3
"""
Raspberry Pi Webserver for Proxmox Unattended Installation
Fetches answer files and scripts from GitHub on each request.

Configuration:
- Port: 8080
- GitHub Repo: buddy9880/pve-unattended-install
- Branch: main
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from urllib.parse import parse_qs, urlparse
from datetime import datetime
import json
import re
import sys
from typing import Optional

# Configuration
PORT = 8080
GITHUB_REPO = "buddy9880/pve-unattended-install"
GITHUB_BRANCH = "main"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
NODE_MAP_FILE = "vars/pve_node.txt"
FIRSTBOOT_FILE = "answer_server/firstboot.sh"

def fetch_from_github(filename: str) -> bytes:
    """
    Fetch a file from GitHub.
    Raises URLError or HTTPError if fetch fails.
    """
    url = f"{GITHUB_RAW_BASE}/{filename}"
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fetching from GitHub: {url}")
    
    with urlopen(url, timeout=10) as response:
        data = response.read()
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Successfully fetched {len(data)} bytes")
        return data

def normalize_mac(mac: str) -> str:
    return mac.lower() if isinstance(mac, str) else ""

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

    node_map = parse_node_map(fetch_from_github(NODE_MAP_FILE).decode("utf-8"))
    for iface in interfaces:
        if not isinstance(iface, dict):
            continue
        node_name = node_map.get(normalize_mac(iface.get("mac")))
        if node_name:
            return node_name

    return None

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Enable logging with timestamps"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} - {format % args}")

    def _send_file(self, data: bytes, content_type: str = "text/plain; charset=utf-8"):
        """Send file data with appropriate headers"""
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle_request(self, body: bytes = b""):
        """Handle both GET and POST requests"""
        parsed_url = urlparse(self.path)
        path = parsed_url.path.rstrip('/')
        if not path:
            path = "/answer"  # Default to answer file for root requests

        if path == "/nodes":
            github_filename = NODE_MAP_FILE
        elif path == "/firstboot":
            github_filename = FIRSTBOOT_FILE
        elif path == "/answer":
            if self.command == "GET":
                node_name = parse_qs(parsed_url.query).get("node", [""])[0]
                if not re.match(r"^[A-Za-z0-9_-]+$", node_name):
                    self.send_error(400, "Use /answer?node=pve-temp for GET testing")
                    return
            else:
                node_name = select_node_from_post(body)
                if not node_name:
                    self.send_error(404, "No answer file configured for this machine")
                    return

            github_filename = f"vars/{node_name}.toml"
        else:
            self.send_error(404, "Endpoint not found. Available: /nodes, /answer, /firstboot")
            return

        try:
            # Fetch file from GitHub
            data = fetch_from_github(github_filename)
            
            # Determine content type - use plain text for browser viewing
            content_type = "text/plain; charset=utf-8"
            
            # Send the file
            self._send_file(data, content_type)
            
        except HTTPError as e:
            error_msg = f"GitHub returned HTTP {e.code} for {github_filename}"
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {error_msg}")
            self.send_error(502, error_msg)
            
        except URLError as e:
            error_msg = f"Failed to fetch from GitHub: {e.reason}"
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {error_msg}")
            self.send_error(502, error_msg)
            
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ERROR: {error_msg}")
            self.send_error(500, error_msg)

    def do_GET(self):
        """Handle GET requests"""
        self._handle_request()

    def do_POST(self):
        """Handle POST requests (Proxmox uses POST for answer file)"""
        # Read and discard the POST body (Proxmox sends system info)
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length > 0 else b""
        
        # Handle the request
        self._handle_request(body)

def main():
    """Main entry point"""
    server = None
    try:
        server = HTTPServer(("0.0.0.0", PORT), Handler)
        
        print("=" * 70)
        print(f"Raspberry Pi Proxmox Webserver Started")
        print("=" * 70)
        print(f"Listening on: http://0.0.0.0:{PORT}/")
        print(f"GitHub Repo:  {GITHUB_REPO}")
        print(f"Branch:       {GITHUB_BRANCH}")
        print()
        print("Endpoints:")
        print(f"  GET  /nodes               → Fetches {NODE_MAP_FILE} from GitHub")
        print(f"  POST /answer              → Selects vars/<node>.toml by MAC address")
        print(f"  GET  /answer?node=pve-temp → Fetches one answer file for testing")
        print(f"  GET  /firstboot           → Fetches {FIRSTBOOT_FILE} from GitHub")
        print()
        print("Note: Files are fetched from GitHub on EVERY request (no caching)")
        print("=" * 70)
        print()
        
        server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n\nShutting down server...")
        if server:
            server.socket.close()
        sys.exit(0)
    except PermissionError:
        print(f"ERROR: Permission denied to bind to port {PORT}")
        print(f"Try running with sudo: sudo python3 {sys.argv[0]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to start server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
