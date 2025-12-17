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
from datetime import datetime
import sys

# Configuration
PORT = 8080
GITHUB_REPO = "buddy9880/pve-unattended-install"
GITHUB_BRANCH = "main"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"

# File mappings: endpoint -> GitHub filename
FILE_MAP = {
    "/answer": "answer.toml",
    "/firstboot": "firstboot.sh"
}

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

    def _handle_request(self):
        """Handle both GET and POST requests"""
        # Normalize path (remove trailing slash)
        path = self.path.rstrip('/')
        if not path:
            path = "/answer"  # Default to answer file for root requests
        
        # Check if this is a known endpoint
        if path not in FILE_MAP:
            self.send_error(404, f"Endpoint '{path}' not found. Available: {', '.join(FILE_MAP.keys())}")
            return
        
        # Get the GitHub filename for this endpoint
        github_filename = FILE_MAP[path]
        
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
        if content_length > 0:
            _ = self.rfile.read(content_length)
        
        # Handle the request
        self._handle_request()

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
        print(f"  POST /answer    → Fetches answer.toml from GitHub")
        print(f"  GET  /answer    → Fetches answer.toml from GitHub")
        print(f"  GET  /firstboot → Fetches firstboot.sh from GitHub")
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
