"""Eingaben aus der App (Häkchen „auf der Uhr“, eigenes Feedback, verschobene Einheiten).

Format: {kind: {key: {"value": ..., "at": ISO-Zeit}}}. value = None bedeutet „gelöscht“.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone

from .config import USERDATA_FILE
from .store import read_text, write_json

KINDS = ("on_watch", "notes", "moves")


def empty() -> dict:
    return {k: {} for k in KINDS}


def _backup_file():
    return USERDATA_FILE.with_name(USERDATA_FILE.name + ".bak")


def _read(path) -> dict | None:
    """Inhalt der Datei. None, wenn sie fehlt, leer oder beschädigt ist."""
    try:
        d = json.loads(read_text(path))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return d if isinstance(d, dict) else None


def load() -> dict:
    d = _read(USERDATA_FILE)
    if d is None and USERDATA_FILE.exists():
        # Beschädigt: nicht als „leer“ behandeln (der nächste Klick würde sonst alles überschreiben),
        # sondern den letzten guten Stand nehmen und die kaputte Datei zur Seite legen.
        d = _read(_backup_file())
        try:
            shutil.copyfile(USERDATA_FILE, USERDATA_FILE.with_name(USERDATA_FILE.name + ".defekt"))
        except OSError:
            pass
    d = d or {}
    return {k: d.get(k, {}) for k in KINDS}


def save(d: dict) -> None:
    if _read(USERDATA_FILE) is not None:  # nur einen lesbaren Stand als Sicherung behalten
        try:
            shutil.copyfile(USERDATA_FILE, _backup_file())
        except OSError:
            pass
    write_json(USERDATA_FILE, d)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def set_entry(kind: str, key: str, value) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unbekannte Art: {kind}")
    d = load()
    d[kind][str(key)] = {"value": value, "at": now_iso()}
    save(d)
    return d


def values(d: dict, kind: str) -> dict:
    """Nur gesetzte Werte (ohne gelöschte Einträge)."""
    return {k: e["value"] for k, e in d.get(kind, {}).items() if e.get("value") is not None}
