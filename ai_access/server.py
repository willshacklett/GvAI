from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path("public")

class Handler(BaseHTTPRequestHandler):
    def send_file(self, path):
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return

        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"GodScore AI Access Live")

        elif self.path == "/latest":
            self.send_file(ROOT / "latest_result.json")

        elif self.path == "/schema":
            self.send_file(ROOT / "godscore_schema.json")

        elif self.path == "/example":
            self.send_file(ROOT / "godscore_example.json")

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    print("Running on http://0.0.0.0:8010")
    HTTPServer(("0.0.0.0", 8010), Handler).serve_forever()
