"""Geplante Einheit als Garmin-Workout (FIT-Datei) für die Uhr.

Die Personal API kann nur lesen. Die Datei kommt per USB auf die Uhr: in den Ordner GARMIN/NewFiles kopieren,
nach dem Trennen steht das Workout unter Training → Workouts.

Aufbau wie der Spickzettel in der App: Schritte mit Zeit oder Distanz, Pulsziel bei allen Schritten außer den
Pausen, Wiederholungen als eigener Schritt, der auf den ersten Schritt des Blocks zurückverweist.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

MESG_FILE_ID, MESG_WORKOUT, MESG_WORKOUT_STEP = 0, 26, 27
INTENSITY = {"warmup": "warmup", "cooldown": "cooldown", "recovery": "rest"}  # alles andere: active
SPORT = {"run": "running", "bike": "cycling"}
HR_OFFSET = 100  # FIT: Werte bis 100 sind % der HFmax, absolute Schläge werden mit +100 gespeichert


def exportable(session: dict) -> bool:
    return session.get("sport") in SPORT and bool(session.get("steps"))


def default_name(session: dict) -> str:
    return f"W{int(session.get('week') or 0):02d} {session.get('weekday', '')} {session.get('title', '')}".strip()[:40]


def file_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", name.replace("×", "x")).strip("_")
    return (safe or "workout")[:60] + ".fit"


def _step(st: dict) -> dict:
    out = {
        "wkt_step_name": str(st.get("label") or "")[:30],
        "intensity": INTENSITY.get(st["type"], "active"),
    }
    if st.get("dist_m"):
        out |= {"duration_type": "distance", "duration_value": round(st["dist_m"] * 100)}  # cm
    else:
        out |= {"duration_type": "time", "duration_value": round(st["min"] * 60) * 1000}  # ms, auf ganze Sekunden
    hr = st.get("hr")
    if hr and hr[0] and st["type"] != "recovery":
        out |= {"target_type": "heart_rate", "target_value": 0,
                "custom_target_value_low": int(hr[0]) + HR_OFFSET, "custom_target_value_high": int(hr[1]) + HR_OFFSET}
    else:
        out |= {"target_type": "open", "target_value": 0}
    pace = st.get("pace")
    notes = [f"Pace {pace} /km" if pace and re.search(r"\d:\d\d", pace) else pace, st.get("note")]
    notes = " · ".join(n for n in notes if n)
    if notes:
        out["notes"] = notes[:120]
    return out


def workout_steps(steps: list[dict], base: int = 0) -> list[dict]:
    """Plan-Schritte → flache Liste von workout_step-Nachrichten (ohne mesg_num und message_index).

    base = Position des ersten Schritts in der Gesamtliste (für verschachtelte Wiederholungen).
    """
    out: list[dict] = []
    for st in steps:
        if st["type"] == "repeat":
            first = base + len(out)
            out.extend(workout_steps(st["steps"], first))
            out.append({"duration_type": "repeat_until_steps_cmplt", "duration_value": first,
                        "target_type": "open", "target_value": int(st["times"])})
        else:
            out.append(_step(st))
    return out


def build(session: dict, name: str | None = None, created: datetime | None = None) -> bytes:
    from garmin_fit_sdk import Encoder

    if not exportable(session):
        raise ValueError("Für diese Einheit gibt es kein Workout.")
    steps = workout_steps(session["steps"])
    created = created or datetime.now(timezone.utc)
    enc = Encoder()
    enc.write_mesg({"mesg_num": MESG_FILE_ID, "type": "workout", "manufacturer": "development", "product": 0,
                    "serial_number": int(created.timestamp()) & 0x7FFFFFFF or 1, "time_created": created})
    enc.write_mesg({"mesg_num": MESG_WORKOUT, "wkt_name": (name or default_name(session))[:40],
                    "sport": SPORT[session["sport"]], "num_valid_steps": len(steps)})
    for i, s in enumerate(steps):
        enc.write_mesg({"mesg_num": MESG_WORKOUT_STEP, "message_index": i, **s})
    return enc.close()
