# ULan – Anleitung

1. **Ordner anlegen**, z. B. `C:\ULan`, und den kompletten Inhalt dieses Projekts hineinkopieren
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

## Anwesenheit und Leave-Sätze
- Oben in der Leiste hat jeder den Knopf **„Ich bin weg“ / „Ich bin zurück“**. „Ich bin weg“ markiert die Person als
  abwesend und spielt am Host-PC einen **zufälligen Leave-Satz** in der Sprache des Kontos ab. Zurückkommen ist still.
- Admins stellen die Sätze im Reiter **Admin** ein („Leave-Sätze“): eine Zeile pro Satz, bis zu 20 pro Sprache, je eine Liste
  für Deutsch und Englisch. `{name}` (auch `{Name}`) wird durch den Namen ersetzt. Leer lassen = Standardsätze.
  Beispiel: `{name} ist kacken gegangen`.
- Im Reiter **Admin** („Anwesenheit“) können Admins den Status jedes Spielers setzen, z. B. für Spieler ohne Konto.
  Abwesende behalten ihre Punkte und können weiter führen.
- Abwesende sind in der App und auf der Nur-Rangliste-Seite als „abwesend“ markiert (abgedunkelt). Die Rangliste zeigt oben
  außerdem „Nicht anwesend: …“.
- `ANNOUNCE_LEAVE = False` in `server.py` schaltet die Leave-Ansage ab (der Status funktioniert weiter).

## Nur-Rangliste-Link (zweiter Port)
- ULan öffnet einen zweiten Port (Standard **8081**), der **nur die Rangliste** zeigt: Namen, Summen und den Führenden (★).
  Ohne Login, nur lesen. Gut für Fernseher, Beamer oder zum Teilen mit Zuschauern.
- Die Adresse steht im Terminal (z. B. `http://192.168.x.x:8081`) und im Reiter „Punkte“.
- Abwesende Spieler sind dort ebenfalls markiert.
- Auf diesem Port ist sonst nichts erreichbar (keine Konten, Hotdogs, Infos, Sounds, keine Haupt-App).
  Mit `LEADERBOARD_PORT = 0` in `server.py` schaltest du ihn ab.
- Soll es auch **außerhalb des LANs** gehen: im Router **nur den Ranglisten-Port** (8081) weiterleiten, niemals `PORT` (8080).
  ULan nutzt kein HTTPS, die Seite ist dann für jeden mit der Adresse sichtbar.

## Sprachen (DE/EN)
- Auf der Login-Seite gibt es den Umschalter **DE | EN**, nach dem Login ändert man die Sprache unter **Einstellungen**. Die Wahl wird pro Konto gespeichert und gilt auch für die
  **Ansagen am Host-PC** (Ankunft und Führung).
- Sätze einstellbar oben in `server.py`: `ARRIVAL_PHRASE`, `ARRIVAL_PHRASE_EN`, `LEADER_PHRASE`, `LEADER_PHRASE_EN`.
  `DEFAULT_LANG` gilt für neue Konten ohne Auswahl und für Spieler ohne Konto.
- Für englische Ansagen nutzt Windows eine englische Stimme, falls installiert (sonst die Standardstimme, dann mit
  deutschem Akzent). `python test_audio.py` zeigt die installierten Stimmen und spielt auch einen englischen Satz.

## Hinweise
- Einstellungen oben in `server.py`: `PORT`, `MAX_SOUND_SIZE`, `ANNOUNCE_ON_LOGIN`, `ANNOUNCE_LEADER`, `LEADER_PHRASE`.
- Daten liegen in `private_data/` (werden nie per HTTP ausgeliefert). Zum Zurücksetzen den Server stoppen und
  die Dateien dort löschen (dann wird der nächste Account wieder Admin).
- Führungs-Ansage: Gespielt wird die Sounddatei des gleichnamigen Kontos (Modus „Sound“ oder „Erst Sound, dann Name“),
  danach immer `LEADER_PHRASE`. Der Name steckt schon in der Phrase und wird deshalb nicht doppelt gesprochen.
- Deutsche Sprachausgabe: Windows nutzt automatisch eine deutsche Stimme (z. B. „Hedda“), falls das deutsche
  Sprachpaket installiert ist, sonst die Standardstimme.
