"""JSON-Dateien sicher schreiben: erst in eine temporäre Datei, dann umbenennen.

So sieht ein gleichzeitiger Leser (App, Coach-Check) nie eine halb geschriebene Datei.
"""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path
from typing import Any


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # Windows: Umbenennen scheitert kurz, solange ein anderer Prozess die Zieldatei gerade liest.
        deadline = time.monotonic() + 5
        while True:
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.01 + random.random() * 0.04)
    finally:
        tmp.unlink(missing_ok=True)


def read_text(path: Path) -> str:
    """Wie path.read_text, wartet aber kurz, wenn die Datei gerade ersetzt wird (Windows: PermissionError)."""
    deadline = time.monotonic() + 2
    while True:
        try:
            return path.read_text(encoding="utf-8")
        except PermissionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.01 + random.random() * 0.02)


def write_json(path: Path, payload: Any, indent: int | None = 1) -> None:
    write_text(path, json.dumps(payload, indent=indent, ensure_ascii=False))
