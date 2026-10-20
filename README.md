# ULan – Guide (English)

ULan is a local intranet for LAN parties. It runs on one Windows PC (the **host**); everyone else opens it in a
browser over the LAN (phone or PC). Features: live scoreboard, schedule, hotdog counter, info text (Wi-Fi password,
server IPs, rules), accounts with Steam links, and sound / name announcements that play **on the host PC**.
The German guide is in `ANLEITUNG.md`.

Source code: https://github.com/jemandX/ULan

## Quick start (6 steps)

1. **Create a folder**, e.g. `C:\ULan`, and copy the whole project into it
   (`server.py`, `start.bat`, `test_audio.py`, and the folders `static`, `sounds`, `private_data`).
2. **Install Python 3** (python.org, tick "Add python.exe to PATH"). No extra packages are needed.
3. **Test the audio first:** run `python test_audio.py` in the folder. You should hear a sound, a name
   announcement, a leader announcement and an English announcement.
4. **Double-click `start.bat`.** On the first start Windows Firewall asks for permission: choose "Allow access"
   (private network). The window shows the addresses, e.g. `http://localhost:8080` and `http://192.168.x.x:8080`.
5. **Open it in the browser** (host: localhost, players: the LAN address) and **register the first account**.
   It automatically becomes admin. Then open the "Admin" tab, click "As player" for each account if you like,
   and add rounds on the "Scores" tab.
6. **Upload a sound and test it:** "Settings" tab → upload a sound → choose sound and mode → Save →
   "Test (on host PC)". Admins also get "Test leader announcement" there.

## Troubleshooting

Send me the terminal lines that start with **`[Host-Audio] Fehler`**, **`[Upload abgelehnt]`**, **`[404]`**,
**`[FEHLER]`** or **`[Führung]`**, plus the output of `python test_audio.py`. (The log lines are in German.)

Common cases:
- **Others cannot open the page:** allow Python in Windows Firewall (private network) and make sure everyone is on the
  same network. Use the `http://192.168.x.x:8080` address shown in the terminal, not `localhost`.
- **Port already in use:** ULan is probably already running in another window, or change `PORT` at the top of `server.py`.
- **No sound on the host:** run `python test_audio.py` and check Windows volume and the default output device.
- **Upload rejected:** only `.wav`, `.mp3`, `.mp4` up to 10 MB are accepted, and the file content must match the extension.

## Languages (DE / EN)

- The **DE | EN** switch is on the login page; after login the language is changed in **Settings**. The choice is saved per account and also
  controls the language of the **announcements on the host PC** (arrival and leader).
- Phrases are set at the top of `server.py`: `ARRIVAL_PHRASE`, `ARRIVAL_PHRASE_EN`, `LEADER_PHRASE`, `LEADER_PHRASE_EN`.
  `DEFAULT_LANG` applies to new accounts without a choice and to players without an account.
- For English announcements Windows uses an English voice if one is installed (otherwise the default voice, which then
  speaks English with a German accent). `python test_audio.py` lists the installed voices.

## Presence and leave phrases

- Everyone has an **"I'm away" / "I'm back"** button in the top bar. Pressing "I'm away" marks the person as absent and plays a
  random **leave phrase** on the host PC, in the language of their account. Coming back is silent.
- Admins edit the phrases in the **Admin** tab ("Leave phrases"): one phrase per line, up to 20 per language, one list for
  German and one for English. `{name}` (any capitalisation) is replaced by the name. An empty list uses the default phrases.
  Example: `{name} went to the loo`.
- Admins can also set the status of any player in the **Admin** tab ("Presence"), e.g. for players without an account.
  Absent players keep their points and can still lead.
- Absent players are marked "away" (dimmed) in the app and on the leaderboard-only page. That page also shows a line
  "Not present: ...".
- Set `ANNOUNCE_LEAVE = False` in `server.py` to turn the leave announcement off (the status itself still works).

## Leaderboard-only link (second port)

ULan also opens a second port (default **8081**) that shows **only the leaderboard**: names, totals and the leader (★).
No login is needed and it is read-only, so you can open it on a TV, a projector or share it with spectators.
The address is printed in the terminal (e.g. `http://192.168.x.x:8081`) and shown on the "Scores" tab.
Absent players are marked there too. Nothing else is reachable on that port: no accounts, hotdogs, info text, sounds or the main app.
Set `LEADERBOARD_PORT = 0` in `server.py` to turn it off.

If you want people **outside your LAN** to see it, forward **only the leaderboard port** (8081) on your router, never `PORT`
(8080). Note that ULan uses plain HTTP and the page is public for everyone who knows the address.

## How it works

- **Roles:** the first registered account is admin. Admins can manage players, rounds, schedule, info text, sounds and
  accounts (make admins, delete users). Normal users can only change points and hotdogs. This is enforced on the server.
- **Arrival announcement:** played when a new account registers (including the very first one) and, if
  `ANNOUNCE_ON_LOGIN = True`, on login. Not on page reload, logout or normal page views.
- **Leader announcement:** played when a *different* player takes first place. The leader is the player with the strictly
  highest total above 0 (sum of rounds). On a tie at the top nothing changes. Someone who already leads and keeps scoring
  triggers nothing. The leader is remembered silently at server start. At most one leader announcement every 10 seconds.
  `ANNOUNCE_LEADER = False` turns it off.
- **Leader sound:** the sound file of the account with the same name (case-insensitive) is played if its mode is "sound"
  or "sound, then name", followed by `LEADER_PHRASE` (which already contains the name, so it is not spoken twice).
  Without a matching account only the phrase is spoken.
- **Highlight:** the leader is highlighted in the ranking and the table (★). On a tie nobody is highlighted.
- **Playback** runs through `powershell.exe` on Windows (MediaPlayer for files, System.Speech for voice). File paths and
  texts are passed via environment variables, never inside the command line. One queue prevents overlapping sounds.

## Settings (top of `server.py`)

| Constant | Meaning |
|---|---|
| `PORT` | Web server port (default 8080) |
| `MAX_SOUND_SIZE` | Maximum upload size in bytes (default 10 MB) |
| `ANNOUNCE_ON_LOGIN` | Announce on login, not only on registration |
| `ANNOUNCE_LEADER` | Announce when someone takes first place |
| `LEADER_PHRASE`, `LEADER_PHRASE_EN` | Leader sentence (`{name}` is replaced) |
| `ARRIVAL_PHRASE`, `ARRIVAL_PHRASE_EN` | Arrival sentence (`{name}` is replaced) |
| `DEFAULT_LANG` | `"de"` or `"en"` for new accounts and players without an account |
| `ANNOUNCE_LEAVE` | Play a leave phrase when someone presses "I'm away" |
| `LEADERBOARD_PORT` | Second port with the public leaderboard only (default 8081, `0` = off) |

## Data and security

- Data lives in `private_data/` (`users.json`, `state.json`, `sessions.json`) and is never served over HTTP.
  To reset everything, stop the server and delete the files there (the next account becomes admin again).
- Passwords are hashed with scrypt and a salt. Sessions use random tokens in an HttpOnly, SameSite=Strict cookie and
  survive a server restart. There is a rate limit against password guessing.
- Uploaded sounds are checked (extension and file header), renamed with a random suffix and never overwritten.
- The server is meant for a trusted local network. It does not use HTTPS.
