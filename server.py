#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LAN-Party-Intranet - Server (nur Python 3 Standardbibliothek, optimiert fuer Windows 10/11)

Start:  python server.py      (oder start.bat doppelklicken)
"""

# ============================ KONFIGURATION ============================
PORT = 8080                                   # Port des Webservers
MAX_SOUND_SIZE = 10 * 1024 * 1024             # maximale Groesse einer Sounddatei in Bytes
ANNOUNCE_ON_LOGIN = True                      # Ansage auch beim Login (nicht nur bei Registrierung)
ANNOUNCE_LEADER = True                        # Ansage bei Wechsel auf Platz 1
LEADER_PHRASE = "{name} übernimmt die Führung"
ARRIVAL_PHRASE = "{name} ist beigetreten"       # Satz bei Ankunft (Modus "Name" bzw. "Sound, dann Name")
# =======================================================================

import base64
import hashlib
import hmac
import http.server
import json
import os
import queue
import re
import secrets
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
import unicodedata
from email.message import Message
from urllib.parse import parse_qs, unquote, urlsplit
from http.cookies import SimpleCookie, CookieError

# ----------------------------- Pfade & Konstanten -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRIVATE_DIR = os.path.join(BASE_DIR, "private_data")
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")
STATIC_DIR = os.path.join(BASE_DIR, "static")
USERS_FILE = os.path.join(PRIVATE_DIR, "users.json")
STATE_FILE = os.path.join(PRIVATE_DIR, "state.json")
SESSIONS_FILE = os.path.join(PRIVATE_DIR, "sessions.json")

SESSION_SECONDS = 30 * 24 * 3600
MAX_JSON_BODY = 100 * 1024
UPLOAD_SLACK = 1024 * 1024            # Platz fuer Multipart-Ueberbau
MAX_DRAIN = 64 * 1024 * 1024
LEADER_COOLDOWN = 10.0                # Sekunden zwischen zwei Fuehrungs-Ansagen
ARRIVAL_COOLDOWN = 8.0                # pro Nutzer
TEST_COOLDOWN = 2.0                   # pro Nutzer
MAX_PLAYERS = 64
MAX_ROUNDS = 30
MAX_SCHEDULE = 60
MAX_INFO = 5000
MODES = ("name", "sound", "both")

SOUND_EXT = (".wav", ".mp3", ".mp4")
SOUND_MIME = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".mp4": "video/mp4"}
STATIC_MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".txt": "text/plain; charset=utf-8",
}
SOUND_RE = re.compile(r"^[A-Za-z0-9_\-.]{1,100}\.(wav|mp3|mp4)$")
USERNAME_RE = re.compile(r"^\w[\w .\-]{1,23}$", re.UNICODE)
STEAM_URL_RE = re.compile(
    r"^https://steamcommunity\.com/(id/[A-Za-z0-9_\-]{2,64}|profiles/[0-9]{17})/?$", re.IGNORECASE
)

LOCK = threading.RLock()
USERS = {}      # id -> dict
SESSIONS = {}   # sha256(token) -> {"uid":..., "exp":...}
STATE = {}
LEADER = {"id": None, "last_announce": 0.0}
ARRIVAL_LAST = {}
TEST_LAST = {}
FAILS = {}      # Rate-Limit: key -> [timestamps]
AUDIO_Q = queue.Queue(maxsize=30)


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class AudioError(Exception):
    pass


# ----------------------------- Hilfsfunktionen -----------------------------
def log(msg):
    try:
        print(msg, flush=True)
    except Exception:
        pass


def atomic_write_json(path, data):
    tmp = path + ".tmp-" + secrets.token_hex(4)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        log("[FEHLER] Datei nicht lesbar: %s (%s)" % (path, e))
        log("        Bitte reparieren oder (wenn nötig) löschen und den Server neu starten.")
        sys.exit(1)


def clean_text(value, label, maxlen, required=True):
    if not isinstance(value, str):
        raise ApiError(400, "%s: ungültiger Wert." % label)
    v = value.strip()
    if required and not v:
        raise ApiError(400, "%s darf nicht leer sein." % label)
    if len(v) > maxlen:
        raise ApiError(400, "%s ist zu lang (max. %d Zeichen)." % (label, maxlen))
    if any(unicodedata.category(c).startswith("C") for c in v):
        raise ApiError(400, "%s enthält ungültige Zeichen." % label)
    return v


def clean_multiline(value, label, maxlen):
    if not isinstance(value, str):
        raise ApiError(400, "%s: ungültiger Wert." % label)
    v = value.replace("\r\n", "\n").replace("\r", "\n")
    if len(v) > maxlen:
        raise ApiError(400, "%s ist zu lang (max. %d Zeichen)." % (label, maxlen))
    for c in v:
        if c not in "\n\t" and unicodedata.category(c).startswith("C"):
            raise ApiError(400, "%s enthält ungültige Zeichen." % label)
    return v


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ----------------------------- Persistenz -----------------------------
def save_users():
    atomic_write_json(USERS_FILE, {"users": list(USERS.values())})


def save_sessions():
    atomic_write_json(SESSIONS_FILE, {"sessions": SESSIONS})


def save_state():
    atomic_write_json(STATE_FILE, STATE)


def bump():
    STATE["rev"] = int(STATE.get("rev", 1)) + 1
    save_state()


def load_all():
    global STATE
    users = load_json(USERS_FILE, {"users": []})
    for u in users.get("users", []):
        USERS[u["id"]] = u
    sess = load_json(SESSIONS_FILE, {"sessions": {}})
    now = time.time()
    for k, v in sess.get("sessions", {}).items():
        if v.get("exp", 0) > now and v.get("uid") in USERS:
            SESSIONS[k] = v
    STATE = load_json(STATE_FILE, {})
    STATE.setdefault("rev", 1)
    STATE.setdefault("players", [])
    STATE.setdefault("rounds", [])
    STATE.setdefault("scores", {})
    STATE.setdefault("hotdogs", {})
    STATE.setdefault("schedule", [])
    STATE.setdefault("info", "")


# ----------------------------- Passwort & Sessions -----------------------------
def scrypt_hash(password, salt):
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=16384, r=8, p=1,
                          maxmem=64 * 1024 * 1024, dklen=32)


def make_password_record(password):
    salt = os.urandom(16)
    return {"salt": salt.hex(), "hash": scrypt_hash(password, salt).hex()}


DUMMY_RECORD = None


def verify_password(user, password):
    global DUMMY_RECORD
    if user is None:
        if DUMMY_RECORD is None:
            DUMMY_RECORD = make_password_record("dummy-passwort")
        scrypt_hash(password, bytes.fromhex(DUMMY_RECORD["salt"]))   # Zeitausgleich
        return False
    calc = scrypt_hash(password, bytes.fromhex(user["salt"]))
    return hmac.compare_digest(calc, bytes.fromhex(user["hash"]))


def find_user(name):
    if not isinstance(name, str):
        return None
    k = name.strip().casefold()
    for u in USERS.values():
        if u["username"].casefold() == k:
            return u
    return None


def create_session(uid):
    token = secrets.token_urlsafe(32)
    with LOCK:
        now = time.time()
        for k in [k for k, v in SESSIONS.items() if v["exp"] < now]:
            del SESSIONS[k]
        SESSIONS[sha(token)] = {"uid": uid, "exp": now + SESSION_SECONDS}
        save_sessions()
    return token


def drop_sessions_of(uid):
    for k in [k for k, v in SESSIONS.items() if v["uid"] == uid]:
        del SESSIONS[k]
    save_sessions()


def session_cookie(token, max_age=SESSION_SECONDS):
    return "session=%s; HttpOnly; SameSite=Strict; Path=/; Max-Age=%d" % (token, max_age)


def rate_limited(key, limit, window):
    now = time.time()
    lst = [t for t in FAILS.get(key, []) if now - t < window]
    FAILS[key] = lst
    if len(lst) >= limit:
        return int(window - (now - lst[0])) + 1
    return 0


def rate_hit(key):
    FAILS.setdefault(key, []).append(time.time())


def me_view(u):
    return {
        "id": u["id"], "username": u["username"], "is_admin": bool(u.get("is_admin")),
        "steam_name": u.get("steam_name", ""), "steam_url": u.get("steam_url", ""),
        "mode": u.get("mode", "name"), "sound": u.get("sound", ""),
    }


# ----------------------------- Sounds -----------------------------
def list_sounds():
    try:
        names = os.listdir(SOUNDS_DIR)
    except OSError:
        return []
    out = []
    for n in names:
        if SOUND_RE.match(n) and ".." not in n and os.path.isfile(os.path.join(SOUNDS_DIR, n)):
            out.append(n)
    return sorted(out, key=str.casefold)


def sound_path(name):
    if not isinstance(name, str) or not name:
        return None
    if not SOUND_RE.match(name) or ".." in name:
        return None
    p = os.path.join(SOUNDS_DIR, name)
    return p if os.path.isfile(p) else None


def sanitize_filename(fn):
    fn = fn.replace("\\", "/").split("/")[-1]
    stem, ext = os.path.splitext(fn)
    stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9_\-]+", "_", stem).strip("_-")[:40] or "sound"
    return stem, ext.lower()


def magic_ok(ext, data):
    if ext == ".wav":
        return data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if ext == ".mp3":
        return data[:3] == b"ID3" or (len(data) > 1 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)
    if ext == ".mp4":
        return data[4:8] == b"ftyp"
    return False


def parse_multipart(body, content_type):
    m = re.search(r'boundary=(?:"([^"]+)"|([^;\s]+))', content_type, re.IGNORECASE)
    if not m:
        raise ApiError(400, "Ungültige Anfrage: Multipart-Boundary fehlt.")
    boundary = (m.group(1) or m.group(2)).encode("latin-1", "replace")
    delim = b"--" + boundary
    fields, files = {}, {}
    for chunk in body.split(delim)[1:]:
        if chunk.startswith(b"--"):
            break
        if chunk.startswith(b"\r\n"):
            chunk = chunk[2:]
        sep = chunk.find(b"\r\n\r\n")
        if sep < 0:
            continue
        head = chunk[:sep].decode("utf-8", "replace")
        data = chunk[sep + 4:]
        if data.endswith(b"\r\n"):
            data = data[:-2]
        msg = Message()
        for line in head.split("\r\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                msg[k.strip()] = v.strip()
        name = msg.get_param("name", header="content-disposition")
        if isinstance(name, tuple):
            name = name[2]
        if not isinstance(name, str):
            continue
        filename = msg.get_filename()
        if filename is not None:
            files[name] = (str(filename), data)
        else:
            fields[name] = data.decode("utf-8", "replace")
    return fields, files


# ----------------------------- Host-Audio (Windows / PowerShell) -----------------------------
PS_FILE = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName PresentationCore
  $path = $env:HOST_AUDIO_FILE
  if (-not $path -or -not (Test-Path -LiteralPath $path)) { throw ('Datei nicht gefunden: ' + $path) }
  $player = New-Object System.Windows.Media.MediaPlayer
  $player.Volume = 1.0
  $player.Open((New-Object System.Uri -ArgumentList $path))
  $player.Play()
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  while (-not $player.NaturalDuration.HasTimeSpan) {
    if ($sw.Elapsed.TotalSeconds -gt 10) { throw 'Zeitlimit: Dauer der Datei nicht lesbar (Codec fehlt oder Datei defekt).' }
    Start-Sleep -Milliseconds 100
  }
  $dur = $player.NaturalDuration.TimeSpan.TotalSeconds
  $player.Volume = 1.0
  $sw.Restart()
  $max = [Math]::Min($dur + 2, 600)
  while (($player.Position.TotalSeconds -lt ($dur - 0.1)) -and ($sw.Elapsed.TotalSeconds -lt $max)) { Start-Sleep -Milliseconds 100 }
  Start-Sleep -Milliseconds 300
  $player.Close()
} catch {
  [Console]::Error.WriteLine($_.Exception.Message)
  exit 1
}
"""

PS_SPEECH = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Speech
  $text = $env:HOST_AUDIO_TEXT
  if (-not $text) { throw 'Kein Text uebergeben.' }
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  foreach ($v in $s.GetInstalledVoices()) {
    if ($v.Enabled -and $v.VoiceInfo.Culture.Name -like 'de*') { $s.SelectVoice($v.VoiceInfo.Name); break }
  }
  $s.Volume = 100
  $s.SetOutputToDefaultAudioDevice()
  $s.Speak($text)
  $s.Dispose()
} catch {
  [Console]::Error.WriteLine($_.Exception.Message)
  exit 1
}
"""

PS_VOICES = r"""
$ErrorActionPreference = 'Stop'
try {
  Add-Type -AssemblyName System.Speech
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  foreach ($v in $s.GetInstalledVoices()) {
    $state = 'deaktiviert'
    if ($v.Enabled) { $state = 'aktiv' }
    Write-Output ($v.VoiceInfo.Name + ' [' + $v.VoiceInfo.Culture.Name + '] ' + $state)
  }
} catch {
  [Console]::Error.WriteLine($_.Exception.Message)
  exit 1
}
"""


def ps_exe():
    root = os.environ.get("SystemRoot", r"C:\Windows")
    p = os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return p if os.path.exists(p) else "powershell.exe"


def decode_output(b):
    if not b:
        return ""
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp850", "replace")


def run_ps(script, extra_env, timeout):
    """Fuehrt ein PowerShell-Skript aus. Werte kommen nur ueber Umgebungsvariablen. Gibt stdout zurueck."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    cmd = [ps_exe(), "-NoProfile", "-NonInteractive", "-STA", "-ExecutionPolicy", "Bypass",
           "-EncodedCommand", encoded]
    env = dict(os.environ)
    env.update(extra_env)
    try:
        r = subprocess.run(cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise AudioError("Zeitüberschreitung (PowerShell hat nicht rechtzeitig geantwortet).")
    except FileNotFoundError:
        raise AudioError("powershell.exe wurde nicht gefunden.")
    except OSError as e:
        raise AudioError("PowerShell konnte nicht gestartet werden: %s" % e)
    err = decode_output(r.stderr).replace("#< CLIXML", "").strip()
    if r.returncode != 0:
        raise AudioError(err or ("PowerShell-Fehlercode %d ohne Meldung." % r.returncode))
    return decode_output(r.stdout)


def play_step(step):
    """Spielt einen Schritt ab: ('file', pfad) oder ('say', text). Wirft AudioError bei Fehlern."""
    kind, value = step
    if kind == "file":
        log("[Host-Audio] spiele %s" % os.path.basename(value))
    else:
        log("[Host-Audio] sage: %s" % value)
    if os.name != "nt":
        log("[Host-Audio] (Simulation: kein Windows, es wird nichts ausgegeben)")
        return
    if kind == "file":
        run_ps(PS_FILE, {"HOST_AUDIO_FILE": value}, 700)
    else:
        run_ps(PS_SPEECH, {"HOST_AUDIO_TEXT": value}, 60)


def audio_worker():
    while True:
        steps = AUDIO_Q.get()
        for step in steps:
            try:
                play_step(step)
            except AudioError as e:
                what = os.path.basename(step[1]) if step[0] == "file" else step[1]
                log("[Host-Audio] Fehler bei '%s': %s" % (what, e))
            except Exception as e:
                log("[Host-Audio] Unerwarteter Fehler: %r" % (e,))


def enqueue(steps, tag):
    if not steps:
        return
    try:
        AUDIO_Q.put_nowait(steps)
    except queue.Full:
        log("[Host-Audio] Warteschlange voll, %s verworfen" % tag)


def steps_for_user(user, mode, sound, name=None):
    name = name or user["username"]
    mode = mode if mode in MODES else "name"
    spath = sound_path(sound) if sound else None
    steps = []
    said = ARRIVAL_PHRASE.replace("{name}", name)
    if mode == "name":
        steps.append(("say", said))
    else:
        if spath:
            steps.append(("file", spath))
        else:
            log("[Host-Audio] Hinweis: Modus '%s' ohne gültige Sounddatei, es wird nur der Name angesagt." % mode)
        if mode == "both" or not spath:
            steps.append(("say", said))
    return steps


def leader_steps(name):
    steps = []
    with LOCK:
        acct = find_user(name)
        if acct and acct.get("mode") in ("sound", "both"):
            sp = sound_path(acct.get("sound", ""))
            if sp:
                steps.append(("file", sp))
    steps.append(("say", LEADER_PHRASE.replace("{name}", name)))
    return steps


def announce_arrival(user):
    now = time.monotonic()
    with LOCK:
        last = ARRIVAL_LAST.get(user["id"], -1e9)
        if now - last < ARRIVAL_COOLDOWN:
            log("[Ankunft] Ansage für %s unterdrückt (Sperre %d s)" % (user["username"], ARRIVAL_COOLDOWN))
            return
        ARRIVAL_LAST[user["id"]] = now
    log("[Ankunft] %s" % user["username"])
    enqueue(steps_for_user(user, user.get("mode", "name"), user.get("sound", "")), "Ankunft")


# ----------------------------- Punkte & Fuehrung -----------------------------
def player_name(pid):
    for p in STATE["players"]:
        if p["id"] == pid:
            return p["name"]
    return "?"


def totals():
    round_ids = {r["id"] for r in STATE["rounds"]}
    res = {}
    for p in STATE["players"]:
        s = STATE["scores"].get(p["id"], {})
        res[p["id"]] = sum(v for rid, v in s.items() if rid in round_ids)
    return res


def leader_status():
    t = totals()
    if not t:
        return ("none", None)
    m = max(t.values())
    if m <= 0:
        return ("none", None)
    top = [pid for pid, v in t.items() if v == m]
    if len(top) == 1:
        return ("unique", top[0])
    return ("tie", top)


def leader_check(initial=False):
    kind, val = leader_status()
    if kind == "none":
        LEADER["id"] = None
        return
    if kind == "tie":
        return
    if val == LEADER["id"]:
        return
    LEADER["id"] = val
    name = player_name(val)
    if initial:
        return
    log("[Führung] Neuer Führender: %s" % name)
    if not ANNOUNCE_LEADER:
        return
    now = time.monotonic()
    if now - LEADER["last_announce"] < LEADER_COOLDOWN:
        log("[Führung] Ansage unterdrückt (Sperre %d s)" % LEADER_COOLDOWN)
        return
    LEADER["last_announce"] = now
    enqueue(leader_steps(name), "Führungs-Ansage")


def top_player_id():
    kind, val = leader_status()
    return val if kind == "unique" else None


# ----------------------------- State-Aktionen -----------------------------
def need_player(pid):
    if not isinstance(pid, str) or not any(p["id"] == pid for p in STATE["players"]):
        raise ApiError(400, "Spieler nicht gefunden.")


def need_round(rid):
    if not isinstance(rid, str) or not any(r["id"] == rid for r in STATE["rounds"]):
        raise ApiError(400, "Runde nicht gefunden.")


def to_int(v, lo, hi, label):
    if isinstance(v, bool):
        raise ApiError(400, "%s: ungültige Zahl." % label)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, str) and re.fullmatch(r"-?\d{1,9}", v.strip()):
        v = int(v.strip())
    if not isinstance(v, int) or v < lo or v > hi:
        raise ApiError(400, "%s: Zahl zwischen %d und %d erwartet." % (label, lo, hi))
    return v


def act_score_set(d):
    need_player(d.get("player"))
    need_round(d.get("round"))
    v = d.get("value")
    cell = STATE["scores"].setdefault(d["player"], {})
    if v is None or v == "":
        cell.pop(d["round"], None)
    else:
        cell[d["round"]] = to_int(v, -1000000, 1000000, "Punkte")


def act_hotdog_add(d):
    need_player(d.get("player"))
    delta = to_int(d.get("delta"), -10, 10, "Änderung")
    cur = int(STATE["hotdogs"].get(d["player"], 0))
    STATE["hotdogs"][d["player"]] = max(0, min(9999, cur + delta))


def act_player_add(d):
    name = clean_text(d.get("name"), "Spielername", 32)
    if len(STATE["players"]) >= MAX_PLAYERS:
        raise ApiError(400, "Zu viele Spieler (max. %d)." % MAX_PLAYERS)
    if any(p["name"].casefold() == name.casefold() for p in STATE["players"]):
        raise ApiError(400, "Diesen Spieler gibt es schon.")
    STATE["players"].append({"id": secrets.token_hex(4), "name": name})


def act_player_delete(d):
    need_player(d.get("id"))
    pid = d["id"]
    STATE["players"] = [p for p in STATE["players"] if p["id"] != pid]
    STATE["scores"].pop(pid, None)
    STATE["hotdogs"].pop(pid, None)


def act_round_add(d):
    name = clean_text(d.get("name"), "Rundenname", 32)
    if len(STATE["rounds"]) >= MAX_ROUNDS:
        raise ApiError(400, "Zu viele Runden (max. %d)." % MAX_ROUNDS)
    if any(r["name"].casefold() == name.casefold() for r in STATE["rounds"]):
        raise ApiError(400, "Diese Runde gibt es schon.")
    STATE["rounds"].append({"id": secrets.token_hex(4), "name": name})


def act_round_delete(d):
    need_round(d.get("id"))
    rid = d["id"]
    STATE["rounds"] = [r for r in STATE["rounds"] if r["id"] != rid]
    for cell in STATE["scores"].values():
        cell.pop(rid, None)


def act_schedule_add(d):
    t = clean_text(d.get("time"), "Uhrzeit", 16)
    title = clean_text(d.get("title"), "Titel", 80)
    if len(STATE["schedule"]) >= MAX_SCHEDULE:
        raise ApiError(400, "Zu viele Zeitplan-Einträge (max. %d)." % MAX_SCHEDULE)
    STATE["schedule"].append({"id": secrets.token_hex(4), "time": t, "title": title})
    STATE["schedule"].sort(key=lambda e: e["time"])


def act_schedule_delete(d):
    sid = d.get("id")
    if not isinstance(sid, str) or not any(e["id"] == sid for e in STATE["schedule"]):
        raise ApiError(400, "Eintrag nicht gefunden.")
    STATE["schedule"] = [e for e in STATE["schedule"] if e["id"] != sid]


def act_info_set(d):
    STATE["info"] = clean_multiline(d.get("text"), "Info-Text", MAX_INFO)


ACTIONS = {
    "score_set": act_score_set, "hotdog_add": act_hotdog_add,
    "player_add": act_player_add, "player_delete": act_player_delete,
    "round_add": act_round_add, "round_delete": act_round_delete,
    "schedule_add": act_schedule_add, "schedule_delete": act_schedule_delete,
    "info_set": act_info_set,
}
ADMIN_ACTIONS = {"player_add", "player_delete", "round_add", "round_delete",
                 "schedule_add", "schedule_delete", "info_set"}


def do_action(user, d):
    act = d.get("action")
    if not isinstance(act, str) or act not in ACTIONS:
        raise ApiError(400, "Unbekannte Aktion.")
    if act in ADMIN_ACTIONS and not user.get("is_admin"):
        raise ApiError(403, "Das darf nur ein Admin.")
    with LOCK:
        ACTIONS[act](d)
        leader_check()
        bump()


def state_json(user):
    with LOCK:
        d = {
            "rev": STATE["rev"],
            "players": STATE["players"],
            "rounds": STATE["rounds"],
            "scores": STATE["scores"],
            "hotdogs": STATE["hotdogs"],
            "schedule": STATE["schedule"],
            "info": STATE["info"],
            "top": top_player_id(),
            "sounds": list_sounds(),
            "users": [{"username": u["username"], "steam_name": u.get("steam_name", ""),
                       "steam_url": u.get("steam_url", "")}
                      for u in sorted(USERS.values(), key=lambda x: x["username"].casefold())],
            "me": me_view(user),
        }
        if user.get("is_admin"):
            d["accounts"] = [{"id": u["id"], "username": u["username"], "is_admin": bool(u.get("is_admin"))}
                             for u in sorted(USERS.values(), key=lambda x: x["username"].casefold())]
        return json.dumps(d, ensure_ascii=False)


# ----------------------------- Netzwerk-Hilfen -----------------------------
def lan_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            ips.add(ip)
    except OSError:
        pass
    return sorted(i for i in ips if not i.startswith("127.") and not i.startswith("169.254."))


# ----------------------------- HTTP-Handler -----------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "LanIntranet"
    sys_version = ""
    timeout = 120

    def log_message(self, *args):
        pass

    # ---- Grundlagen ----
    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def do_HEAD(self):
        self.dispatch("HEAD")

    def common_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; media-src 'self'; img-src 'self' data:; "
                         "style-src 'self'; script-src 'self'; frame-ancestors 'none'")

    def send_bytes(self, status, body, ctype, headers=None, cache="no-store"):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.common_headers()
        for k, v in (headers or []):
            self.send_header(k, v)
        self.end_headers()
        if self.method != "HEAD":
            self.wfile.write(body)

    def send_json(self, obj, status=200, headers=None):
        text = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
        self.send_bytes(status, text.encode("utf-8"), "application/json; charset=utf-8", headers)

    def origin_ok(self):
        o = self.headers.get("Origin")
        if not o:
            return True
        return urlsplit(o).netloc.lower() == self.headers.get("Host", "").lower()

    def drain_unread(self):
        if self.method != "POST" or self.body_read:
            return
        self.body_read = True
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return
        if n <= 0 or n > MAX_DRAIN:
            return
        try:
            while n > 0:
                chunk = self.rfile.read(min(65536, n))
                if not chunk:
                    break
                n -= len(chunk)
        except (OSError, ValueError):
            pass

    def dispatch(self, method):
        self.method = method
        self.body_read = False
        parts = urlsplit(self.path)
        path = parts.path
        try:
            if method == "POST" and not self.origin_ok():
                raise ApiError(403, "Ungültiger Origin.")
            if path.startswith("/api/"):
                self.api(method, path, parse_qs(parts.query))
            elif path == "/favicon.ico":
                self.send_bytes(204, b"", "image/x-icon")
            elif path.startswith("/sounds/"):
                self.serve_sound(path[len("/sounds/"):])
            else:
                self.serve_static(path)
        except ApiError as e:
            if e.status == 404:
                log("[404] %s %s" % (method, self.path))
            try:
                self.drain_unread()
                if path.startswith("/api/"):
                    self.send_json({"error": e.message}, e.status)
                else:
                    self.send_bytes(e.status, (str(e.status) + " " + e.message).encode("utf-8"),
                                    "text/plain; charset=utf-8")
            except (OSError, ValueError):
                pass
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, socket.timeout):
            pass
        except Exception:
            log("[FEHLER] Unerwarteter Fehler bei %s %s" % (method, self.path))
            log(traceback.format_exc())
            try:
                self.send_json({"error": "Interner Serverfehler (Details im Terminal)."}, 500)
            except (OSError, ValueError):
                pass

    # ---- Eingaben lesen ----
    def read_body(self, limit):
        cl = self.headers.get("Content-Length")
        if cl is None:
            raise ApiError(411, "Content-Length fehlt.")
        try:
            n = int(cl)
        except ValueError:
            raise ApiError(400, "Ungültige Content-Length.")
        if n < 0 or n > limit:
            raise ApiError(413, "Anfrage zu groß.")
        self.body_read = True
        buf = bytearray()
        while len(buf) < n:
            chunk = self.rfile.read(min(65536, n - len(buf)))
            if not chunk:
                raise ApiError(400, "Anfrage unvollständig (Verbindung unterbrochen).")
            buf.extend(chunk)
        return bytes(buf)

    def read_json(self):
        ctype = (self.headers.get("Content-Type") or "").lower()
        if not ctype.startswith("application/json"):
            raise ApiError(415, "Content-Type application/json erwartet.")
        body = self.read_body(MAX_JSON_BODY)
        if not body:
            return {}
        try:
            d = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, "Ungültiges JSON.")
        if not isinstance(d, dict):
            raise ApiError(400, "JSON-Objekt erwartet.")
        return d

    def current_user(self):
        c = self.headers.get("Cookie")
        if not c:
            return None
        try:
            sc = SimpleCookie()
            sc.load(c)
        except CookieError:
            return None
        m = sc.get("session")
        if not m or not m.value:
            return None
        with LOCK:
            s = SESSIONS.get(sha(m.value))
            if not s or s["exp"] < time.time():
                return None
            return USERS.get(s["uid"])

    def require_user(self):
        u = self.current_user()
        if not u:
            raise ApiError(401, "Bitte anmelden.")
        return u

    # ---- API ----
    def api(self, method, path, query):
        if method == "POST" and path == "/api/login":
            return self.api_login()
        if method == "POST" and path == "/api/register":
            return self.api_register()
        user = self.require_user()
        if method == "GET" and path == "/api/me":
            return self.send_json({"me": me_view(user)})
        if method in ("GET", "HEAD") and path == "/api/state":
            rev = query.get("rev", [""])[0]
            if rev.isdigit() and int(rev) == STATE["rev"]:
                return self.send_json({"changed": False, "rev": STATE["rev"]})
            return self.send_json(state_json(user))
        if method == "POST":
            if path == "/api/logout":
                return self.api_logout()
            if path == "/api/action":
                do_action(user, self.read_json())
                return self.send_json(state_json(user))
            if path == "/api/settings":
                return self.api_settings(user)
            if path == "/api/upload":
                return self.api_upload(user)
            if path == "/api/sounds/delete":
                return self.api_sound_delete(user)
            if path == "/api/test/announce":
                return self.api_test_announce(user)
            if path == "/api/test/leader":
                return self.api_test_leader(user)
            if path == "/api/admin/user/admin":
                return self.api_user_admin(user)
            if path == "/api/admin/user/delete":
                return self.api_user_delete(user)
        raise ApiError(404, "Unbekannte API-Route.")

    def api_register(self):
        d = self.read_json()
        ip = self.client_address[0]
        wait = rate_limited("reg:" + ip, 15, 600)
        if wait:
            raise ApiError(429, "Zu viele Registrierungen. Bitte in %d s erneut versuchen." % wait)
        rate_hit("reg:" + ip)
        name = clean_text(d.get("username"), "Benutzername", 24)
        pw = d.get("password")
        if not USERNAME_RE.match(name):
            raise ApiError(400, "Benutzername: 2-24 Zeichen (Buchstaben, Zahlen, Leerzeichen, _ . -).")
        if not isinstance(pw, str) or len(pw) < 6 or len(pw) > 128:
            raise ApiError(400, "Das Passwort muss 6 bis 128 Zeichen lang sein.")
        rec = make_password_record(pw)
        with LOCK:
            if find_user(name):
                raise ApiError(409, "Dieser Benutzername ist schon vergeben.")
            first = len(USERS) == 0
            user = {"id": secrets.token_hex(8), "username": name, "salt": rec["salt"], "hash": rec["hash"],
                    "is_admin": first, "steam_name": "", "steam_url": "", "mode": "name", "sound": "",
                    "created": int(time.time())}
            USERS[user["id"]] = user
            save_users()
            bump()
        log("[Konto] Registriert: %s%s" % (name, " (Admin, erster Account)" if first else ""))
        token = create_session(user["id"])
        announce_arrival(user)
        self.send_json({"me": me_view(user)}, headers=[("Set-Cookie", session_cookie(token))])

    def api_login(self):
        d = self.read_json()
        name, pw = d.get("username"), d.get("password")
        if not isinstance(name, str) or not isinstance(pw, str) or len(name) > 64 or len(pw) > 256:
            raise ApiError(400, "Ungültige Eingabe.")
        ip = self.client_address[0]
        k1, k2 = "ipuser:%s|%s" % (ip, name.strip().casefold()), "ip:" + ip
        wait = max(rate_limited(k1, 6, 300), rate_limited(k2, 30, 600))
        if wait:
            log("[Login] Gesperrt (zu viele Versuche) von %s" % ip)
            raise ApiError(429, "Zu viele Fehlversuche. Bitte in %d s erneut versuchen." % wait)
        with LOCK:
            u = find_user(name)
        if not verify_password(u, pw):
            rate_hit(k1)
            rate_hit(k2)
            log("[Login] Fehlgeschlagen für '%s' von %s" % (name[:30], ip))
            raise ApiError(401, "Benutzername oder Passwort falsch.")
        FAILS.pop(k1, None)
        token = create_session(u["id"])
        if ANNOUNCE_ON_LOGIN:
            announce_arrival(u)
        self.send_json({"me": me_view(u)}, headers=[("Set-Cookie", session_cookie(token))])

    def api_logout(self):
        c = self.headers.get("Cookie") or ""
        try:
            sc = SimpleCookie()
            sc.load(c)
            m = sc.get("session")
        except CookieError:
            m = None
        if m and m.value:
            with LOCK:
                if SESSIONS.pop(sha(m.value), None) is not None:
                    save_sessions()
        self.read_json()
        self.send_json({"ok": True}, headers=[("Set-Cookie", session_cookie("", 0))])

    def check_mode_sound(self, d, default_mode, default_sound):
        mode = d.get("mode", default_mode)
        sound = d.get("sound", default_sound)
        if mode not in MODES:
            raise ApiError(400, "Ungültiger Ansage-Modus.")
        if not isinstance(sound, str):
            raise ApiError(400, "Ungültige Sound-Auswahl.")
        if sound and sound not in list_sounds():
            raise ApiError(400, "Diese Sounddatei gibt es nicht (mehr).")
        return mode, sound

    def api_settings(self, user):
        d = self.read_json()
        steam_name = clean_text(d.get("steam_name", ""), "Steam-Handle", 32, required=False)
        url = clean_text(d.get("steam_url", ""), "Steam-Link", 200, required=False)
        if url:
            m = STEAM_URL_RE.match(url)
            if not m:
                raise ApiError(400, "Der Steam-Link muss mit https://steamcommunity.com/id/... "
                                    "oder https://steamcommunity.com/profiles/... beginnen.")
            url = "https://steamcommunity.com/" + m.group(1)
        mode, sound = self.check_mode_sound(d, "name", "")
        with LOCK:
            u = USERS[user["id"]]
            u["steam_name"], u["steam_url"], u["mode"], u["sound"] = steam_name, url, mode, sound
            save_users()
            bump()
        self.send_json(state_json(u))

    def api_upload(self, user):
        ctype = self.headers.get("Content-Type") or ""
        fname = "?"

        def reject(status, reason):
            log("[Upload abgelehnt] %s (Nutzer: %s, Datei: %s)" % (reason, user["username"], fname))
            raise ApiError(status, reason)

        if not ctype.lower().startswith("multipart/form-data"):
            reject(400, "Der Upload muss als multipart/form-data gesendet werden.")
        try:
            length = int(self.headers.get("Content-Length") or "")
        except ValueError:
            reject(411, "Content-Length fehlt.")
        if length > MAX_SOUND_SIZE + UPLOAD_SLACK:
            reject(413, "Datei zu groß (max. %d MB)." % (MAX_SOUND_SIZE // (1024 * 1024)))
        body = self.read_body(MAX_SOUND_SIZE + UPLOAD_SLACK)
        try:
            fields, files = parse_multipart(body, ctype)
        except ApiError as e:
            reject(e.status, e.message)
        entry = files.get("sound") or (next(iter(files.values())) if files else None)
        if not entry:
            reject(400, "Keine Datei im Upload gefunden.")
        fname, data = entry
        stem, ext = sanitize_filename(fname)
        if ext not in SOUND_EXT:
            reject(400, "Dateityp nicht erlaubt (nur .wav, .mp3, .mp4).")
        if not data:
            reject(400, "Die Datei ist leer.")
        if len(data) > MAX_SOUND_SIZE:
            reject(413, "Datei zu groß (max. %d MB)." % (MAX_SOUND_SIZE // (1024 * 1024)))
        if not magic_ok(ext, data):
            reject(400, "Der Inhalt passt nicht zur Endung %s (keine gültige Audiodatei)." % ext)
        os.makedirs(SOUNDS_DIR, exist_ok=True)
        with LOCK:
            while True:
                final_name = "%s_%s%s" % (stem, secrets.token_hex(4), ext)
                final_path = os.path.join(SOUNDS_DIR, final_name)
                if not os.path.exists(final_path):
                    break
            tmp = final_path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, final_path)
            bump()
        log("[Upload] %s von %s (%d Bytes)" % (final_name, user["username"], len(data)))
        out = json.loads(state_json(user))
        out["uploaded"] = final_name
        self.send_json(out)

    def api_sound_delete(self, user):
        if not user.get("is_admin"):
            raise ApiError(403, "Das darf nur ein Admin.")
        d = self.read_json()
        name = d.get("name")
        p = sound_path(name)
        if not p:
            raise ApiError(400, "Sounddatei nicht gefunden.")
        with LOCK:
            os.remove(p)
            for u in USERS.values():
                if u.get("sound") == name:
                    u["sound"] = ""
            save_users()
            bump()
        log("[Sound] gelöscht: %s (von %s)" % (name, user["username"]))
        self.send_json(state_json(user))

    def test_lock(self, user):
        now = time.monotonic()
        with LOCK:
            if now - TEST_LAST.get(user["id"], -1e9) < TEST_COOLDOWN:
                raise ApiError(429, "Bitte kurz warten (Test-Sperre %d s)." % TEST_COOLDOWN)
            TEST_LAST[user["id"]] = now

    def api_test_announce(self, user):
        d = self.read_json()
        self.test_lock(user)
        mode, sound = self.check_mode_sound(d, user.get("mode", "name"), user.get("sound", ""))
        steps = steps_for_user(user, mode, sound)
        log("[Test] Ansage von %s (Modus %s)" % (user["username"], mode))
        enqueue(steps, "Test")
        note = ""
        if mode != "name" and not sound:
            note = " (Keine Sounddatei gewählt, es wird nur der Name angesagt.)"
        self.send_json({"ok": True, "message": "Test läuft am Host-PC." + note})

    def api_test_leader(self, user):
        if not user.get("is_admin"):
            raise ApiError(403, "Das darf nur ein Admin.")
        d = self.read_json()
        self.test_lock(user)
        name = clean_text(d.get("name", user["username"]), "Name", 32)
        log("[Test] Führungs-Ansage für %s" % name)
        enqueue(leader_steps(name), "Test Führung")
        self.send_json({"ok": True, "message": "Führungs-Test läuft am Host-PC."})

    def api_user_admin(self, user):
        if not user.get("is_admin"):
            raise ApiError(403, "Das darf nur ein Admin.")
        d = self.read_json()
        uid, flag = d.get("id"), d.get("admin")
        if not isinstance(flag, bool):
            raise ApiError(400, "Ungültiger Wert.")
        with LOCK:
            target = USERS.get(uid) if isinstance(uid, str) else None
            if not target:
                raise ApiError(400, "Nutzer nicht gefunden.")
            if not flag and target.get("is_admin") and sum(1 for u in USERS.values() if u.get("is_admin")) <= 1:
                raise ApiError(400, "Es muss mindestens ein Admin übrig bleiben.")
            target["is_admin"] = flag
            save_users()
            bump()
        log("[Konto] %s ist jetzt %s (durch %s)" % (target["username"], "Admin" if flag else "kein Admin",
                                                    user["username"]))
        self.send_json(state_json(user))

    def api_user_delete(self, user):
        if not user.get("is_admin"):
            raise ApiError(403, "Das darf nur ein Admin.")
        d = self.read_json()
        uid = d.get("id")
        with LOCK:
            target = USERS.get(uid) if isinstance(uid, str) else None
            if not target:
                raise ApiError(400, "Nutzer nicht gefunden.")
            if uid == user["id"]:
                raise ApiError(400, "Du kannst dich nicht selbst löschen.")
            del USERS[uid]
            drop_sessions_of(uid)
            save_users()
            bump()
        log("[Konto] gelöscht: %s (durch %s)" % (target["username"], user["username"]))
        self.send_json(state_json(user))

    # ---- Dateien ausliefern ----
    def decode_path(self, raw):
        dec = unquote(raw)
        bad = ("%" in dec or "\\" in dec or "\x00" in dec or ":" in dec
               or any(p == ".." for p in dec.split("/")))
        low = dec.lower()
        if bad or "private_data" in low or low.endswith((".py", ".pyc", ".bat")):
            log("[Schutz] Blockierter Pfad: %s %s" % (self.method, self.path))
            raise ApiError(404, "Nicht gefunden.")
        return dec

    def serve_static(self, path):
        if self.method not in ("GET", "HEAD"):
            raise ApiError(405, "Methode nicht erlaubt.")
        rel = self.decode_path(path.lstrip("/"))
        if rel == "":
            rel = "index.html"
        root = os.path.realpath(STATIC_DIR)
        full = os.path.realpath(os.path.join(root, *[p for p in rel.split("/") if p not in ("", ".")]))
        try:
            inside = os.path.commonpath([full, root]) == root
        except ValueError:
            inside = False
        ext = os.path.splitext(full)[1].lower()
        if not inside or ext not in STATIC_MIME or not os.path.isfile(full):
            raise ApiError(404, "Nicht gefunden.")
        self.send_file(full, STATIC_MIME[ext], "no-cache")

    def serve_sound(self, raw):
        if self.method not in ("GET", "HEAD"):
            raise ApiError(405, "Methode nicht erlaubt.")
        self.require_user()
        name = self.decode_path(raw)
        p = sound_path(name)
        if not p:
            raise ApiError(404, "Nicht gefunden.")
        self.send_file(p, SOUND_MIME[os.path.splitext(name)[1].lower()], "private, max-age=0")

    def send_file(self, fpath, mime, cache):
        try:
            f = open(fpath, "rb")
        except OSError:
            raise ApiError(404, "Nicht gefunden.")
        with f:
            size = os.fstat(f.fileno()).st_size
            start, end, status = 0, size - 1, 200
            rng = self.headers.get("Range")
            if rng:
                m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng.strip())
                if m and (m.group(1) or m.group(2)):
                    if m.group(1) == "":
                        start = max(0, size - int(m.group(2)))
                        end = size - 1
                    else:
                        start = int(m.group(1))
                        end = int(m.group(2)) if m.group(2) else size - 1
                    end = min(end, size - 1)
                    if start >= size or start > end:
                        self.send_response(416)
                        self.send_header("Content-Range", "bytes */%d" % size)
                        self.send_header("Content-Length", "0")
                        self.common_headers()
                        self.end_headers()
                        return
                    status = 206
            length = end - start + 1 if size else 0
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", cache)
            if status == 206:
                self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
            self.common_headers()
            self.end_headers()
            if self.method == "HEAD" or not length:
                return
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = (os.name != "nt")
    request_queue_size = 64


def main():
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass
    os.makedirs(PRIVATE_DIR, exist_ok=True)
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    if not os.path.isdir(STATIC_DIR):
        log("[FEHLER] Ordner 'static' fehlt neben server.py.")
        sys.exit(1)
    load_all()
    leader_check(initial=True)
    threading.Thread(target=audio_worker, daemon=True).start()
    try:
        server = Server(("0.0.0.0", PORT), Handler)
    except OSError as e:
        log("[FEHLER] Port %d kann nicht geöffnet werden: %s" % (PORT, e))
        log("        Läuft der Server schon in einem anderen Fenster? Sonst PORT oben in server.py ändern.")
        sys.exit(1)
    log("=" * 60)
    log(" LAN-Party-Intranet läuft")
    log("   Dieser PC:  http://localhost:%d" % PORT)
    for ip in lan_ips():
        log("   Im LAN:     http://%s:%d" % (ip, PORT))
    log(" Beenden mit Strg+C")
    if os.name != "nt":
        log(" HINWEIS: Kein Windows erkannt. Host-Audio wird nur simuliert.")
    leader = player_name(LEADER["id"]) if LEADER["id"] else "niemand"
    log(" Aktueller Führender (still gemerkt): %s" % leader)
    log("=" * 60)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("\nServer beendet.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
