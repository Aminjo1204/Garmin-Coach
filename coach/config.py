"""Athletenprofil, Zonen, Paces und Pfade.

Persönliche Werte stehen in `athlete.json` (nicht im Repo). Fehlt die Datei, wird `athlete.example.json` verwendet.
Zonen werden aus der Schwellen-Herzfrequenz (lthr) berechnet, Paces aus der 5-km-Zeit –
beides lässt sich in athlete.json auch direkt überschreiben ("zones_run", "paces").
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FIT_DIR = DATA_DIR / "fit"
PLAN_FILE = ROOT / "plan" / "plan.json"
FEEDBACK_DIR = ROOT / "feedback"          # Coach-Feedback von Claude: <activityId>.json
NOTES_FILE = FEEDBACK_DIR / "notes.json"   # allgemeine Coach-Nachrichten
SYNC_INFO_FILE = DATA_DIR / "sync_info.json"
USERDATA_FILE = ROOT / "userdata" / "userdata.json"  # Eingaben aus der App
ATHLETE_FILE = ROOT / "athlete.json"
ATHLETE_EXAMPLE = ROOT / "athlete.example.json"


def _load_athlete() -> dict:
    src = ATHLETE_FILE if ATHLETE_FILE.exists() else ATHLETE_EXAMPLE
    return json.loads(src.read_text(encoding="utf-8"))


_A = _load_athlete()

ATHLETE = {k: _A.get(k) for k in ("name", "age", "weight_kg", "height_cm", "hr_rest", "hr_max", "lthr",
                                  "vo2max_start", "vo2max_goal", "five_k", "coach_context")}

PLAN_START = date.fromisoformat(_A["plan_start"])   # Montag von Woche 1
PLAN_INTRO_DAYS = int(_A.get("plan_intro_days", 3))  # lockere Einstiegstage vor Woche 1 (0 = keine)
PLAN_WEEKS = 12

ZONE_NAMES = ["Regeneration", "Grundlage", "Tempo", "Schwelle", "VO2max"]


def _zones_from_lthr(lthr: int) -> list[dict]:
    b1, b2, b3 = round(0.77 * lthr), round(0.855 * lthr), round(0.935 * lthr)
    bounds = [(0, b1 - 1), (b1, b2 - 1), (b2, b3), (b3 + 1, lthr), (lthr + 1, 250)]
    return [{"z": i + 1, "name": ZONE_NAMES[i], "lo": lo, "hi": hi} for i, (lo, hi) in enumerate(bounds)]


def _zones_from_list(lst: list) -> list[dict]:
    return [{"z": i + 1, "name": ZONE_NAMES[i], "lo": lo, "hi": hi} for i, (lo, hi) in enumerate(lst)]


RUN_ZONES = _zones_from_list(_A["zones_run"]) if _A.get("zones_run") else _zones_from_lthr(int(_A["lthr"]))
_BIKE_OFF = int(_A.get("bike_hr_offset", 10))  # Rad-Puls liegt bei gleicher Belastung tiefer
BIKE_ZONES = [{**z, "lo": max(0, z["lo"] - _BIKE_OFF) if z["lo"] else 0,
               "hi": z["hi"] - _BIKE_OFF if z["hi"] < 250 else 250} for z in RUN_ZONES]


def _mmss(sec: float) -> str:
    sec = round(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def _paces_from_5k(five_k: str) -> dict:
    m, s = five_k.split(":")
    p = (int(m) * 60 + int(s)) / 5  # s/km
    r = lambda a, b: f"{_mmss(p + a)}–{_mmss(p + b)}"
    return {
        "easy": r(105, 145), "long": r(105, 135), "tempo": r(55, 68), "threshold": r(28, 43),
        "vo2": r(-12, -2), "vo2_fast": r(-22, -12), "short": r(-35, -22), "short_fast": r(-42, -27),
        "strides": f"~{_mmss(p - 50)}", "five_k": _mmss(p),
    }


PACES = _paces_from_5k(_A["five_k"]) | (_A.get("paces") or {})

# Pulsziele für Workout-Schritte, abgeleitet aus den Zonen
_Z = {z["z"]: z for z in RUN_ZONES}
_BZ = {z["z"]: z for z in BIKE_ZONES}
HR_MAX = int(_A["hr_max"])
HR_TARGETS = {
    "wu": [_Z[2]["lo"] - 15, _Z[2]["lo"] + 10],
    "easy": [_Z[2]["lo"], _Z[2]["hi"]],
    "tempo": [_Z[3]["lo"], _Z[3]["hi"]],
    "thr": [_Z[4]["lo"], _Z[4]["hi"]],
    "vo2": [_Z[5]["lo"], HR_MAX - 5],
    "short": [_Z[5]["lo"] - 5, HR_MAX - 5],
    "jog": [0, _Z[2]["hi"]],
    "bike_z2": [_BZ[2]["lo"], _BZ[2]["hi"]],
}
EASY_CAP_RUN = _Z[2]["hi"]
EASY_CAP_BIKE = _BZ[2]["hi"]
VO2_HR = _Z[5]["lo"]
THR_LO, THR_HI = _Z[4]["lo"], _Z[4]["hi"]

RUN_TYPES = {"running", "treadmill_running", "trail_running", "track_running", "street_running", "indoor_running", "virtual_run"}
BIKE_TYPES = {"cycling", "indoor_cycling", "road_biking", "virtual_ride", "mountain_biking", "gravel_cycling", "e_bike_fitness"}
STRENGTH_TYPES = {"strength_training", "hiit", "indoor_cardio", "fitness_equipment"}


def sport_of(type_key: str) -> str:
    if type_key in RUN_TYPES or "running" in type_key:
        return "run"
    if type_key in BIKE_TYPES or "cycling" in type_key or "biking" in type_key:
        return "bike"
    if type_key in STRENGTH_TYPES:
        return "strength"
    return "other"


def zones_for(sport: str):
    return BIKE_ZONES if sport == "bike" else RUN_ZONES


def zone_of(hr: float | None, sport: str = "run") -> int | None:
    if not hr:
        return None
    for z in zones_for(sport):
        if z["lo"] <= hr <= z["hi"]:
            return z["z"]
    return 5 if hr > 0 else None
