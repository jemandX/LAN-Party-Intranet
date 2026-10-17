# LAN-Party-Intranet – Anleitung

1. **Ordner anlegen**, z. B. `C:\LAN-Party`, und den kompletten Inhalt dieses Projekts hineinkopieren
   (`server.py`, `start.bat`, `test_audio.py`, Ordner `static`, `sounds`, `private_data`).
2. **Python 3 installieren** (python.org, Haken bei „Add python.exe to PATH“). Es werden keine Pakete gebraucht.
3. **Audio zuerst testen:** `python test_audio.py` im Ordner ausführen. Du solltest einen Sound, eine Namensansage
   und eine Führungs-Ansage hören.
4. **`start.bat` doppelklicken.** Beim ersten Start fragt die Windows-Firewall: „Zugriff zulassen“ (privates Netzwerk).
   Im Fenster stehen die Adressen, z. B. `http://localhost:8080` und `http://192.168.x.x:8080`.
5. **Im Browser öffnen** (Host: localhost, Mitspieler: die LAN-Adresse) und den **ersten Account registrieren**.
   Er wird automatisch Admin. Danach unter „Admin“ bei Bedarf „Als Spieler“ klicken und Runden anlegen.
6. **Sound hochladen und testen:** Reiter „Einstellungen“ → Sound hochladen → Sound und Modus wählen → Speichern →
   „Testen (am Host-PC)“. Admins haben dort zusätzlich „Führungs-Ansage testen“.

## Wenn etwas nicht klappt
Schick mir die Terminalzeilen, die mit **`[Host-Audio] Fehler`**, **`[Upload abgelehnt]`**, **`[404]`**,
**`[FEHLER]`** oder **`[Führung]`** beginnen, plus die Ausgabe von `python test_audio.py`.

## Hinweise
- Einstellungen oben in `server.py`: `PORT`, `MAX_SOUND_SIZE`, `ANNOUNCE_ON_LOGIN`, `ANNOUNCE_LEADER`, `LEADER_PHRASE`.
- Daten liegen in `private_data/` (werden nie per HTTP ausgeliefert). Zum Zurücksetzen den Server stoppen und
  die Dateien dort löschen (dann wird der nächste Account wieder Admin).
- Führungs-Ansage: Gespielt wird die Sounddatei des gleichnamigen Kontos (Modus „Sound“ oder „Erst Sound, dann Name“),
  danach immer `LEADER_PHRASE`. Der Name steckt schon in der Phrase und wird deshalb nicht doppelt gesprochen.
- Deutsche Sprachausgabe: Windows nutzt automatisch eine deutsche Stimme (z. B. „Hedda“), falls das deutsche
  Sprachpaket installiert ist, sonst die Standardstimme.
