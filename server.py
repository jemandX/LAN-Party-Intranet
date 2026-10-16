"""LAN-Party-Intranet: liefert index.html aus und speichert den Stand in state.json.

Start:  python server.py
Dann im Browser:  http://<IP-des-Host-PCs>:8080
Benötigt nur Python 3 (keine zusätzlichen Pakete).
"""
import json
import hashlib
import hmac
import os
import queue
import re
import secrets
import socket
import tempfile
import threading
import time
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie

PORT = 8080
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(ROOT, "state.json")
USERS_FILE = os.path.join(ROOT, "users.json")
MAX_REQUEST_SIZE = 1_000_000
lock = threading.Lock()
users_lock = threading.Lock()
sessions_lock = threading.Lock()
sessions = {}
login_attempts_lock = threading.Lock()
login_attempts = {}
SOUNDS_DIR = os.path.join(ROOT, "sounds")
os.makedirs(SOUNDS_DIR, exist_ok=True)
SOUND_MODES = {"name", "sound", "both"}

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


def load_users():
    try:
        with open(USERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_users(users):
    fd, temp_path = tempfile.mkstemp(prefix="users-", suffix=".tmp", dir=ROOT)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, USERS_FILE)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def username_key(name):
    return name.casefold()


def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return salt.hex(), digest.hex()


def verify_password(password, user):
    try:
        salt = bytes.fromhex(user["salt"])
        expected = bytes.fromhex(user["password_hash"])
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (KeyError, ValueError, TypeError):
        return False


def public_user(user):
    return {
        "username": user["username"],
        "role": user["role"],
        "sound_mode": user.get("sound_mode", "name"),
        "sound_file": user.get("sound_file", ""),
        "steam_handle": user.get("steam_handle", ""),
        "avatar_url": user.get("avatar_url", "")
    }


def current_user(handler):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
        token = cookie.get("lanparty_session").value if cookie.get("lanparty_session") else ""
    except Exception:
        token = ""
    with sessions_lock:
        session = sessions.get(token)
        if not session:
            return None
        if session["expires"] < time.time():
            sessions.pop(token, None)
            return None
        return session["user"]


def issue_session(user):
    token = secrets.token_urlsafe(32)
    with sessions_lock:
        sessions[token] = {"user": user, "expires": time.time() + 30 * 24 * 60 * 60}
    return token


def require_user(handler):
    user = current_user(handler)
    if user is None:
        handler.send_json(401, {"error": "Bitte zuerst anmelden."})
    return user


def admin_state_change(old, new):
    return (old.get("schedule") == new.get("schedule")
            and old.get("rounds") == new.get("rounds")
            and old.get("info") == new.get("info")
            and len(old.get("players", [])) == len(new.get("players", []))
            and all(a.get("name") == b.get("name")
                    and len(a.get("scores", [])) == len(b.get("scores", []))
                    for a, b in zip(old.get("players", []), new.get("players", []))))


def available_sounds():
    try:
        return sorted(name for name in os.listdir(SOUNDS_DIR)
                      if name.lower().endswith((".wav", ".mp3", ".mp4"))
                      and os.path.isfile(os.path.join(SOUNDS_DIR, name)))
    except OSError:
        return []


def clean(d, rev):
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

    def end_headers(self):
        # Korrekte Mime-Types für Audio-Dateien im Ordner /sounds/ setzen
        if self.path.startswith("/sounds/"):
            if self.path.endswith(".wav"):
                self.send_header("Content-Type", "audio/wav")
            elif self.path.endswith(".mp3"):
                self.send_header("Content-Type", "audio/mpeg")
            elif self.path.endswith(".mp4"):
                self.send_header("Content-Type", "audio/mp4")
        super().end_headers()

    def send_json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_REQUEST_SIZE:
            raise ValueError("Ungültige Anfragegröße")
        data = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON-Objekt erwartet")
        return data

    def set_session_cookie(self, token):
        self.send_header("Set-Cookie", f"lanparty_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000")

    def login_ip_limited(self):
        now = time.time()
        ip = self.client_address[0]
        with login_attempts_lock:
            recent = [stamp for stamp in login_attempts.get(ip, []) if now - stamp < 60]
            login_attempts[ip] = recent
            return len(recent) >= 5

    def record_login_failure(self, success=False):
        ip = self.client_address[0]
        with login_attempts_lock:
            if success:
                login_attempts.pop(ip, None)
            else:
                login_attempts.setdefault(ip, []).append(time.time())

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/state":
            with lock:
                return self.send_json(200, load())
        if path == "/api/me":
            user = current_user(self)
            return self.send_json(200, {"user": public_user(user) if user else None})
        if path == "/api/sounds":
            return self.send_json(200, {"sounds": available_sounds()})
        if path == "/users.json" or path.startswith("/users-"):
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/sound/upload":
            user = require_user(self)
            if user is None:
                return
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                return self.send_json(400, {"error": "Multipart-Daten erwartet."})
            try:
                import email.message
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                msg = email.message.EmailMessage()
                msg["Content-Type"] = content_type
                msg.set_payload(body)
                
                filename = None
                file_data = None
                if msg.is_multipart():
                    for part in msg.iter_parts():
                        disp = part.get("Content-Disposition", "")
                        if "filename=" in disp:
                            filename = part.get_filename()
                            file_data = part.get_payload(decode=True)
                            break
                if not filename or not file_data:
                    return self.send_json(400, {"error": "Keine Datei gefunden."})
                
                filename = os.path.basename(filename)
                if not filename.lower().endswith((".wav", ".mp3", ".mp4")):
                    return self.send_json(400, {"error": "Nur .wav, .mp3 oder .mp4 Dateien erlaubt."})
                
                filepath = os.path.join(SOUNDS_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(file_data)
                return self.send_json(200, {"ok": True, "filename": filename})
            except Exception:
                return self.send_json(400, {"error": "Upload fehlgeschlagen."})

        if path == "/api/me/settings":
            user = require_user(self)
            if user is None:
                return
            try:
                data = self.read_json()
                mode = data.get("sound_mode", user.get("sound_mode", "name"))
                filename = data.get("sound_file", user.get("sound_file", ""))
                steam = str(data.get("steam_handle", user.get("steam_handle", "")))[:50]
                avatar = str(data.get("avatar_url", user.get("avatar_url", "")))[:255]

                if mode not in SOUND_MODES or (filename and filename not in available_sounds()):
                    return self.send_json(400, {"error": "Ungültige Sound-Einstellung."})

                key = username_key(user["username"])
                with users_lock:
                    users = load_users()
                    if key in users:
                        users[key]["sound_mode"] = mode
                        users[key]["sound_file"] = filename
                        users[key]["steam_handle"] = steam
                        users[key]["avatar_url"] = avatar
                        save_users(users)
                user.update({"sound_mode": mode, "sound_file": filename, "steam_handle": steam, "avatar_url": avatar})
                with sessions_lock:
                    for session in sessions.values():
                        if username_key(session["user"]["username"]) == key:
                            session["user"] = dict(user)
                return self.send_json(200, {"user": public_user(user)})
            except Exception:
                return self.send_json(400, {"error": "Fehler beim Speichern der Einstellungen."})

        try:
            request_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self.send_json(400, {"error": "Ungültige Anfragegröße."})
        if request_length < 0 or request_length > MAX_REQUEST_SIZE:
            return self.send_json(413, {"error": "Anfrage ist zu groß."})

        if path == "/api/register":
            try:
                data = self.read_json()
                username = data.get("username", "")
                password = data.get("password", "")
                mode = data.get("sound_mode", "name")
                filename = data.get("sound_file", "")
                steam = str(data.get("steam_handle", ""))[:50]
                avatar = str(data.get("avatar_url", ""))[:255]
                
                if not isinstance(username, str):
                    return self.send_json(400, {"error": "Ungültiger Benutzername."})
                username = username.strip()
                if len(username) < 2 or len(username) > 20 or any(ord(ch) < 32 for ch in username):
                    return self.send_json(400, {"error": "Der Benutzername muss 2 bis 20 Zeichen lang sein."})
                if not isinstance(password, str) or len(password) < 6:
                    return self.send_json(400, {"error": "Das Passwort muss mindestens 6 Zeichen lang sein."})
                if mode not in SOUND_MODES or (filename and filename not in available_sounds()):
                    return self.send_json(400, {"error": "Ungültige Sound-Einstellung."})

                salt, password_hash = hash_password(password)
                key = username_key(username)
                with users_lock:
                    users = load_users()
                    if key in users:
                        return self.send_json(409, {"error": "Dieser Benutzername ist bereits vergeben."})
                    user = {
                        "username": username,
                        "role": "admin" if not users else "user",
                        "salt": salt,
                        "password_hash": password_hash,
                        "sound_mode": mode,
                        "sound_file": filename,
                        "steam_handle": steam,
                        "avatar_url": avatar
                    }
                    users[key] = user
                    save_users(users)
                    with lock:
                        state = load()
                        state["players"].append({"name": username, "scores": [0] * state["rounds"]})
                        state["rev"] = state.get("rev", 0) + 1
                        with open(STATE_FILE, "w", encoding="utf-8") as f:
                            json.dump(state, f, ensure_ascii=False, indent=2)
                token = issue_session(public_user(user))
                body = json.dumps({"user": public_user(user)}, ensure_ascii=False).encode("utf-8")
                self.send_response(201)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.set_session_cookie(token)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception:
                return self.send_json(400, {"error": "Ungültige Registrierungsdaten."})

        if path == "/api/login":
            if self.login_ip_limited():
                return self.send_json(429, {"error": "Zu viele Fehlversuche. Bitte warte eine Minute."})
            try:
                data = self.read_json()
                username = data.get("username", "")
                password = data.get("password", "")
                if not isinstance(username, str) or not isinstance(password, str):
                    raise ValueError("Ungültige Zugangsdaten")
                with users_lock:
                    user = load_users().get(username_key(username.strip()))
                if not user or not verify_password(password, user):
                    self.record_login_failure()
                    return self.send_json(401, {"error": "Benutzername oder Passwort ist falsch."})
                self.record_login_failure(success=True)
                p_user = public_user(user)
                token = issue_session(p_user)
                body = json.dumps({"user": p_user}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.set_session_cookie(token)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception:
                return self.send_json(400, {"error": "Ungültige Anmeldedaten."})

        if path == "/api/logout":
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            morsel = cookie.get("lanparty_session")
            if morsel:
                with sessions_lock:
                    sessions.pop(morsel.value, None)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Set-Cookie", "lanparty_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")
            self.send_header("Content-Length", "11")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        if path in ("/api/sound/test", "/api/sound/arrive"):
            if path == "/api/sound/arrive":
                user = require_user(self)
                if user is None:
                    return
                return self.send_json(200, {"ok": True, "sound_file": user.get("sound_file", ""), "sound_mode": user.get("sound_mode", "name")})
            
            user = current_user(self)
            try:
                data = self.read_json()
                mode = data.get("sound_mode", user.get("sound_mode", "name") if user else "name")
                selected = data.get("sound_file", user.get("sound_file", "") if user else "")
                return self.send_json(200, {"ok": True, "sound_file": selected, "sound_mode": mode})
            except Exception:
                return self.send_json(400, {"error": "Ungültige Sound-Einstellung."})

        if path == "/api/state":
            user = require_user(self)
            if user is None:
                return
            try:
                data = self.read_json()
                with lock:
                    old = load()
                    new = clean(data, old.get("rev", 0) + 1)
                    if user["role"] != "admin" and not admin_state_change(old, new):
                        return self.send_json(403, {"error": "Dafür fehlen die Rechte."})
                    with open(STATE_FILE, "w", encoding="utf-8") as f:
                        json.dump(new, f, ensure_ascii=False, indent=2)
                return self.send_json(200, new)
            except Exception:
                return self.send_json(400, {"error": "Ungültige Daten"})

        return self.send_error(404)

    def log_message(self, *args):
        pass


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