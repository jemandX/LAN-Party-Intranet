"""LAN-Party-Intranet: liefert index.html aus und speichert den Stand in state.json.

Start:  python server.py
Dann im Browser:  http://<IP-des-Host-PCs>:8080
Benötigt nur Python 3 (keine zusätzlichen Pakete).
"""
import json
import os
import socket
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

PORT = 8080
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(ROOT, "state.json")
lock = threading.Lock()

DEFAULT = {
    "rev": 0,
    "schedule": [
        {"time": "12:00", "title": "Aufwärmen (freies Spiel)"},
        {"time": "13:00", "title": "Hotdog-Pause"},
        {"time": "14:00", "title": "Runde 1"},
        {"time": "15:30", "title": "Pause"},
        {"time": "16:00", "title": "Runde 2"},
        {"time": "17:30", "title": "Finale"},
    ],
    "rounds": 2,
    "players": [
        {"name": "Spieler 1", "scores": [0, 0]},
        {"name": "Spieler 2", "scores": [0, 0]},
        {"name": "Spieler 3", "scores": [0, 0]},
    ],
    "hotdogs": 0,
    "info": "WLAN-Passwort, Server-IPs und Regeln hier eintragen.",
}


def num(x):
    try:
        return int(float(x))
    except Exception:
        return 0


def load():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(DEFAULT))


def clean(d, rev):
    """Prüft und begrenzt die Daten, die ein Browser schickt."""
    return {
        "rev": rev,
        "schedule": [
            {"time": str(x.get("time", ""))[:5], "title": str(x.get("title", ""))[:80]}
            for x in d["schedule"][:50]
        ],
        "rounds": max(1, min(num(d["rounds"]), 20)),
        "players": [
            {
                "name": str(p.get("name", ""))[:30],
                "scores": [num(s) for s in p.get("scores", [])[:20]],
            }
            for p in d["players"][:30]
        ],
        "hotdogs": max(0, min(num(d.get("hotdogs", 0)), 999)),
        "info": str(d.get("info", ""))[:2000],
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/state":
            with lock:
                return self.send_json(200, load())
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/state":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", 0))
        if length > 1_000_000:
            return self.send_error(413)
        try:
            data = json.loads(self.rfile.read(length))
            with lock:
                new = clean(data, load().get("rev", 0) + 1)
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    json.dump(new, f, ensure_ascii=False, indent=2)
            return self.send_json(200, new)
        except Exception:
            return self.send_json(400, {"error": "Ungültige Daten"})

    def log_message(self, *args):
        pass  # keine Konsolenflut


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return socket.gethostbyname(socket.gethostname())


if __name__ == "__main__":
    print("LAN-Party-Intranet läuft.")
    print(f"  Auf diesem PC:  http://localhost:{PORT}")
    print(f"  Für alle anderen: http://{local_ip()}:{PORT}")
    print("Beenden mit Strg+C.")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
