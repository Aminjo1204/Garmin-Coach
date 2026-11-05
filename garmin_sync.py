"""Holt deine Garmin-Daten (Aktivitäten, FIT-Details, Schlaf, HRV, Body Battery) nach ./data.

Aufruf:  .venv\\Scripts\\python.exe garmin_sync.py
"""

import sys

from coach.sync import sync

if __name__ == "__main__":
    info = sync()
    print("\nFertig." if info["ok"] else f"\nMit Fehlern: {info['errors']}")
    sys.exit(0 if info["ok"] else 1)
