import http.cookiejar
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request

import server

root = tempfile.mkdtemp()
server.ROOT = root
server.USERS_FILE = os.path.join(root, "users.json")
server.STATE_FILE = os.path.join(root, "state.json")
server.SOUNDS_DIR = os.path.join(root, "sounds")
os.mkdir(server.SOUNDS_DIR)
httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = "http://127.0.0.1:%s" % httpd.server_port
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def post(path, data):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return opener.open(request)


assert post("/api/register", {
    "username": "Admin1", "password": "secret12", "sound_mode": "name", "sound_file": ""
}).status == 201
assert json.load(opener.open(base + "/api/me"))["user"]["role"] == "admin"
assert post("/api/logout", {}).status == 200
assert post("/api/register", {"username": "UserTwo", "password": "secret12"}).status == 201
state = json.load(opener.open(base + "/api/state"))
state["info"] = "Manipulation"
try:
    post("/api/state", state)
    raise AssertionError("Nicht-Admin durfte Infos ändern")
except urllib.error.HTTPError as error:
    assert error.code == 403
assert post("/api/sound/test", {
    "username": "UserTwo", "sound_mode": "name", "sound_file": ""
}).status == 202
assert json.load(opener.open(base + "/api/me"))["user"]["username"] == "UserTwo"
httpd.shutdown()
httpd.server_close()
print("HTTP-Smoke-Test erfolgreich")
