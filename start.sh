#!/usr/bin/env sh
# Startet die Coach-App (macOS/Linux) und öffnet den Browser.
cd "$(dirname "$0")"
( sleep 1.5; (command -v open >/dev/null && open http://127.0.0.1:5057) || xdg-open http://127.0.0.1:5057 ) >/dev/null 2>&1 &
exec .venv/bin/python app.py
