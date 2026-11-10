@echo off
rem Gibt die Coach-App ueber Tailscale fuer deine eigenen Geraete frei (HTTPS, nicht oeffentlich).
rem Einmal ausfuehren reicht: Die Freigabe bleibt auch nach einem Neustart bestehen.
rem Anleitung: docs\handy.md
setlocal
set "TS=tailscale"
where tailscale >nul 2>nul
if errorlevel 1 (
  if exist "%ProgramFiles%\Tailscale\tailscale.exe" (
    set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
  ) else (
    echo Tailscale ist nicht installiert. Bitte zuerst die Schritte in docs\handy.md machen.
    pause
    exit /b 1
  )
)
"%TS%" serve --bg http://127.0.0.1:5057
if errorlevel 1 (
  echo.
  echo Die Freigabe hat nicht geklappt. Bist du in Tailscale angemeldet und ist HTTPS im Konto aktiviert?
  echo Siehe docs\handy.md, Schritt 3.
  pause
  exit /b 1
)
echo.
echo Fertig. Diese Adresse am Handy in Safari oeffnen:
"%TS%" serve status
echo.
echo Freigabe wieder beenden:  tailscale serve reset
pause
