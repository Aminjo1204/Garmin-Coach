"""Eingaben aus der App (Häkchen „auf der Uhr“, eigenes Feedback, verschobene Einheiten).

Format: {kind: {key: {"value": ..., "at": ISO-Zeit}}}. value = None bedeutet „gelöscht“.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import USERDATA_FILE

KINDS = ("on_watch", "notes", "moves")


def empty() -> dict:
    return {k: {} for k in KINDS}


def load() -> dict:
    try:
        d = json.loads(USERDATA_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        d = {}
    return {k: d.get(k, {}) for k in KINDS}


def save(d: dict) -> None:
    USERDATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERDATA_FILE.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")


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
