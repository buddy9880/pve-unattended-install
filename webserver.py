from http.server import BaseHTTPRequestHandler, HTTPServer
import os

PORT = 8080
ROOT = os.getcwd()
SERVE_FILE = None  # Will be set from user input

def read_answers(path) -> bytes:
    with open(path, "rb") as f:
        return f.read()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # quiet

    def _send_toml(self, data: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # Handy for manual testing in a browser/curl
        try:
            if SERVE_FILE is None:
                self.send_error(500, "Server not properly configured")
                return
            data = read_answers(SERVE_FILE)
            self._send_toml(data)
        except FileNotFoundError:
            filename = os.path.basename(SERVE_FILE) if SERVE_FILE else "file"
            self.send_error(404, f"{filename} not found")

    def do_POST(self):
        # Proxmox expects the TOML answer file as the POST response body
        length = int(self.headers.get("Content-Length", "0"))
        _ = self.rfile.read(length)  # ignore posted JSON payload (optional: log it)

        try:
            if SERVE_FILE is None:
                self.send_error(500, "Server not properly configured")
                return
            data = read_answers(SERVE_FILE)
            self._send_toml(data)
        except FileNotFoundError:
            filename = os.path.basename(SERVE_FILE) if SERVE_FILE else "file"
            self.send_error(404, f"{filename} not found")

if __name__ == "__main__":
    while True:
        filename = input("Enter the filename to serve: ").strip()
        
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
            print(f"Serving {filename} on http://0.0.0.0:{PORT}/")
            HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
            break
        else:
            print(f"Error: File '{filepath}' not found. Please try again.")
