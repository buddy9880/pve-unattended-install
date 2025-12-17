from http.server import BaseHTTPRequestHandler, HTTPServer
import os
from datetime import datetime

PORT = 8080
ROOT = os.getcwd()
SERVE_FILE = None  # Will be set from user input
FIRSTBOOT_FILE = "firstboot.sh"  # Fixed filename in current directory

def read_file(path) -> bytes:
    with open(path, "rb") as f:
        return f.read()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Enable logging with timestamps
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {format % args}")

    def _send_file(self, data: bytes, content_type: str = "text/plain; charset=utf-8"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            # Route: /firstboot.sh
            if self.path == "/firstboot.sh":
                firstboot_path = os.path.join(ROOT, FIRSTBOOT_FILE)
                if not os.path.isfile(firstboot_path):
                    self.send_error(404, f"{FIRSTBOOT_FILE} not found")
                    return
                data = read_file(firstboot_path)
                self._send_file(data)
                return
            
            # Route: / or /answers (serve answer file)
            if self.path in ["/", "/answers"]:
                if SERVE_FILE is None:
                    self.send_error(500, "Server not properly configured")
                    return
                data = read_file(SERVE_FILE)
                self._send_file(data)
                return
            
            # No matching route
            self.send_error(404, "Not Found")
        except FileNotFoundError:
            self.send_error(404, "File not found")

    def do_POST(self):
        # Proxmox expects the TOML answer file as the POST response body
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length)  # ignore posted JSON payload (optional: log it)

        try:
            if SERVE_FILE is None:
                self.send_error(500, "Server not properly configured")
                return
            data = read_file(SERVE_FILE)
            self._send_file(data)
        except FileNotFoundError:
            filename = os.path.basename(SERVE_FILE) if SERVE_FILE else "file"
            self.send_error(404, f"{filename} not found")

if __name__ == "__main__":
    # Check if firstboot.sh exists
    firstboot_path = os.path.join(ROOT, FIRSTBOOT_FILE)
    firstboot_exists = os.path.isfile(firstboot_path)
    
    if not firstboot_exists:
        print(f"WARNING: {FIRSTBOOT_FILE} not found in current directory!")
        print(f"         Requests to /firstboot.sh will return 404\n")
    
    while True:
        filename = input("Enter the answer filename to serve: ").strip()
        
        if not filename:
            print("Error: Filename cannot be empty. Please enter a valid filename.")
            continue
        
        # Support both absolute and relative paths
        if os.path.isabs(filename):
            filepath = filename
        else:
            filepath = os.path.join(ROOT, filename)
        
        # Validate file exists
        if os.path.isfile(filepath):
            SERVE_FILE = filepath
            print(f"\n{'='*60}")
            print(f"Webserver started on http://0.0.0.0:{PORT}/")
            print(f"{'='*60}")
            print(f"Files:")
            print(f"  - Answer file:      {filename}")
            print(f"  - Firstboot script: {FIRSTBOOT_FILE} {'✓' if firstboot_exists else '✗ (not found)'}")
            print(f"\nEndpoints:")
            print(f"  POST /              → {filename}")
            print(f"  GET  /              → {filename}")
            print(f"  GET  /answers       → {filename}")
            if firstboot_exists:
                print(f"  GET  /firstboot.sh  → {FIRSTBOOT_FILE}")
            print(f"{'='*60}\n")
            HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
            break
        else:
            print(f"Error: File '{filepath}' not found. Please try again.")
