## **LAN-Party Intranet (ULan)**
This is a LAN-Party Intranet for small LAN parties.
It's got a hotdog counter and a leaderboard w/ sounds.
It's also in German and English.

## FEATURES
- **Live leaderboard** with points per round, the current leader is highlighted (★)
- **Hotdog counter** for every player
- **Schedule** and an **info page** (Wi-Fi password, server IPs, rules) that everyone sees live
- **Accounts** with login and logout. The first account becomes admin, admins can manage players, rounds, schedule, sounds and other accounts
- **Steam links:** every player can add a Steam handle and profile link, shown in a "Players & Steam" list
- **Sounds and announcements on the host PC:** upload `.wav`, `.mp3` or `.mp4` (max. 10 MB). When someone joins or takes first place, the server PC plays their sound and/or says their name
- **German and English:** switch at the top right, the choice also sets the language of the announcements
- Works on phones and PCs, dark design, no internet needed, no extra Python packages

## INSTRUCTIONS
Download at the [Releases Page](https://github.com/jemandX/Lan-Intranet/releases)

For the server use a Windows PC w/ Windows 10 or higher that has a speaker and is connected to your LAN-Network.
Python is mandatory on the server PC.

### Quick start
1. Unzip the download into a folder, e.g. `C:\ULan`.
2. Install **Python 3** from [python.org](https://www.python.org/downloads/) and tick "Add python.exe to PATH".
3. Optional but recommended: run `python test_audio.py` to check that sound and voice work on the server PC.
4. Double-click `start.bat`. On the first start Windows Firewall asks for permission, choose "Allow access" (private network).
5. The window shows the addresses, e.g. `http://localhost:8080` and `http://192.168.x.x:8080`. Open the LAN address on the other devices.
6. Register the **first account** (it becomes admin), add players and rounds, upload a sound under "Settings" and press "Test".


## SETTINGS
At the top of `server.py` you can change:

| Constant | Meaning |
|---|---|
| `PORT` | Web server port (default 8080) |
| `MAX_SOUND_SIZE` | Maximum upload size (default 10 MB) |
| `ANNOUNCE_ON_LOGIN` | Announce on login, not only on registration |
| `ANNOUNCE_LEADER` | Announce when someone takes first place |
| `ARRIVAL_PHRASE` / `ARRIVAL_PHRASE_EN` | Sentence when someone joins, `{name}` is replaced |
| `LEADER_PHRASE` / `LEADER_PHRASE_EN` | Sentence when someone takes the lead |
| `DEFAULT_LANG` | `"de"` or `"en"` for new accounts |

## TROUBLESHOOTING
- **Others can't open the page:** allow Python in Windows Firewall and use the `192.168.x.x` address from the terminal, not `localhost`.
- **No sound:** run `python test_audio.py`, then check Windows volume and the default output device. For English announcements an English Windows voice is used if installed.
- **Port already in use:** ULan is probably running in another window, or change `PORT` in `server.py`.
- **Something else:** copy the terminal lines starting with `[Host-Audio] Fehler`, `[Upload abgelehnt]`, `[404]` or `[FEHLER]` when you report an issue.

## NOTES
- Data is stored in `private_data/` and is never served over the network. Delete the files there (with the server stopped) to reset everything.
- Passwords are hashed with scrypt. ULan uses plain HTTP and is meant for a trusted local network only.
- Everything runs on the Python standard library, there is nothing to `pip install`.
