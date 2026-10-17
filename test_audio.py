#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Audio-Test fuer den Windows-Host-PC. Starten mit:  python test_audio.py
Spielt (1) eine Sounddatei aus sounds/, (2) eine Namensansage, (3) eine Fuehrungs-Ansage ab
und zeigt die genaue Fehlermeldung, falls etwas nicht klappt.
"""
import math
import os
import struct
import sys
import tempfile
import wave

import server

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

results = []


def step(title, func):
    print("\n--- %s ---" % title)
    try:
        func()
        print("OK (kein Fehler gemeldet). Hast du etwas gehört?")
        results.append((title, True, ""))
    except server.AudioError as e:
        print("FEHLER: %s" % e)
        results.append((title, False, str(e)))
    except Exception as e:
        print("UNERWARTETER FEHLER: %r" % (e,))
        results.append((title, False, repr(e)))


def make_beep():
    path = os.path.join(tempfile.gettempdir(), "lan_test_beep.wav")
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        frames = b"".join(struct.pack("<h", int(12000 * math.sin(2 * math.pi * 660 * i / 22050)))
                          for i in range(22050))
        w.writeframes(frames)
    return path


def main():
    print("ULan Audio-Test")
    print("Betriebssystem: %s | Python %s" % (os.name, sys.version.split()[0]))
    if os.name != "nt":
        print("HINWEIS: Das ist kein Windows. Es wird nur simuliert.")
    else:
        print("PowerShell: %s (vorhanden: %s)" % (server.ps_exe(), os.path.exists(server.ps_exe())))

    print("\n--- Installierte Windows-Stimmen ---")
    if os.name == "nt":
        try:
            print(server.run_ps(server.PS_VOICES, {}, 30).strip() or "(keine Stimmen gefunden)")
            print("Eine deutsche Stimme (de-DE) wird automatisch gewählt, falls vorhanden.")
        except server.AudioError as e:
            print("FEHLER beim Lesen der Stimmen: %s" % e)

    sounds = server.list_sounds()
    if sounds:
        sound_path = os.path.join(server.SOUNDS_DIR, sounds[0])
        print("\nVerwende Sound aus sounds/: %s" % sounds[0])
    else:
        sound_path = make_beep()
        print("\nIm Ordner sounds/ liegt noch nichts. Es wird ein Test-Piepton verwendet.")

    step("1) Sounddatei abspielen", lambda: server.play_step(("file", sound_path)))
    step("2) Namensansage", lambda: server.play_step(("say", "Test Spieler")))
    step("3) Führungs-Ansage",
         lambda: server.play_step(("say", server.LEADER_PHRASE.replace("{name}", "Test Spieler"))))

    step("4) Englische Ansage (englische Stimme, falls installiert)",
         lambda: server.play_step(("say", server.ARRIVAL_PHRASE_EN.replace("{name}", "Test Player"), "en")))

    print("\n================ ZUSAMMENFASSUNG ================")
    for title, ok, err in results:
        print("%s  %s%s" % ("OK    " if ok else "FEHLER", title, "" if ok else "  ->  " + err))
    if all(ok for _, ok, _ in results):
        print("\nAlles meldet OK. Hörst du trotzdem nichts: Windows-Lautstärke, Standard-Ausgabegerät,")
        print("und ob der Sound in Windows wirklich laut genug ist (Lautstärkemixer) prüfen.")
    else:
        print("\nBitte schicke mir die FEHLER-Zeilen oben (Zeilen mit '->' oder 'FEHLER:').")
    if sys.stdin and sys.stdin.isatty():
        input("\nEnter drücken zum Beenden ...")


if __name__ == "__main__":
    main()
