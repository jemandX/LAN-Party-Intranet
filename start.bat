@echo off
chcp 65001 >nul
cd /d "%~dp0"
title LAN-Party-Intranet
where python >nul 2>nul
if not errorlevel 1 goto haspython
where py >nul 2>nul
if not errorlevel 1 goto haspy
echo Python 3 wurde nicht gefunden. Bitte von python.org installieren
echo und den Haken bei "Add python.exe to PATH" setzen.
goto ende
:haspython
python server.py
goto ende
:haspy
py -3 server.py
:ende
echo.
echo Server beendet. Taste druecken zum Schliessen.
pause >nul
