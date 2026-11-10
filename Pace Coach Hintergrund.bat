@echo off
rem Startet die Coach-App ohne Fenster (z. B. im Autostart, damit das Handy sie jederzeit erreicht).
rem Beenden: Task-Manager, Prozess "pythonw.exe".
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" app.py
