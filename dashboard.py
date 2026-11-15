"""Read-only local dashboard. Serve only on loopback unless explicitly overridden."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HTML = (ROOT / 'dashboard.html').read_bytes()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            body, mime, code = HTML, 'text/html; charset=utf-8', 200
        elif self.path == '/app.js':
            body, mime, code = (ROOT / 'app.js').read_bytes(), 'text/javascript; charset=utf-8', 200
        elif self.path == '/api/status':
            try:
                body = Path(os.getenv('DASHBOARD_DATA', str(ROOT / 'dashboard.json'))).read_bytes()
                json.loads(body)
                code = 200
            except (OSError, ValueError):
                body, code = b'{"status":"waiting","players":[],"recent_alerts":[],"active_games":0}', 200
            mime = 'application/json; charset=utf-8'
        else:
            body, mime, code = b'Not found', 'text/plain', 404
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'")
        self.end_headers()
        self.wfile.write(body)

if __name__ == '__main__':
    address = os.getenv('DASHBOARD_HOST', '127.0.0.1')
    port = int(os.getenv('DASHBOARD_PORT', '8765'))
    print(f'Dashboard: http://{address}:{port}')
    ThreadingHTTPServer((address, port), Handler).serve_forever()
