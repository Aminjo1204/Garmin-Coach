"""Fragebogen in der App: Vorschläge aus den Garmin-Daten, Antworten prüfen, athlete.json schreiben, Plan erzeugen.

Ein bestehender Plan wird vorher als plan/plan-<Zeit>.json gesichert. Verschiebungen und Häkchen aus der App
gehören zu den alten Einheiten und werden zurückgesetzt. Feedback und Notizen zu Aktivitäten bleiben.
"""

from __future__ import annotations

import json
import re
import shutil
import statistics as st
import subprocess
import sys
from datetime import date, datetime, timedelta

from . import userdata
from .config import ATHLETE_FILE, DATA_DIR, FIT_DIR, GOALS, NOTES_FILE, PLAN_FILE, ROOT, sport_of
from .plan_builder import MAX_WEEKS, MIN_WEEKS


class SetupError(ValueError):
    pass


def _load(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def next_monday(d: date | None = None) -> date:
    d = d or date.today()
    return d + timedelta(days=(7 - d.weekday()) % 7 or 7)


def tanaka(age: int) -> int:
    return round(208 - 0.7 * age)


def suggestions() -> dict:
    """Werte zum Vorausfüllen: bestehendes Profil plus Schätzungen aus den Garmin-Daten."""
    profile = _load(ATHLETE_FILE)
    acts = _load(DATA_DIR / "activities.json", []) or []
    daily = _load(DATA_DIR / "daily_summaries.json", []) or []
    runs = [a for a in acts if sport_of(a["activityType"]["typeKey"]) == "run"]
    max_hr = max((a.get("maxHR") or 0 for a in runs), default=0) or None
    rhr = [((d.get("heartRate") or {}).get("restingValue")) for d in sorted(daily, key=lambda d: d["calendarDate"])[-14:]]
    rhr = [x for x in rhr if x]
    vo2 = None
    if FIT_DIR.exists():
        latest = None
        for a in sorted(acts, key=lambda a: a["startTimeLocal"]):
            f = _load(FIT_DIR / f"{a['activityId']}.json") if (FIT_DIR / f"{a['activityId']}.json").exists() else None
            if f and f.get("vo2max"):
                latest = f["vo2max"]
        vo2 = latest
    # Wochenumfang der letzten 4 Wochen → Niveau
    since = (date.today() - timedelta(days=28)).isoformat()
    km4 = sum((a.get("distance") or 0) for a in runs if a["startTimeLocal"][:10] >= since) / 1000 / 4
    level = 0 if km4 < 15 else 1 if km4 < 25 else 2 if km4 < 40 else 3
    return {
        "profile": profile,
        "has_plan": PLAN_FILE.exists(),
        "has_data": bool(acts),
        "goals": GOALS,
        "next_monday": next_monday().isoformat(),
        "min_weeks": MIN_WEEKS, "max_weeks": MAX_WEEKS,
        "suggest": {
            "hr_max_seen": max_hr,
            "hr_rest": round(st.mean(rhr)) if rhr else None,
            "vo2max": round(vo2, 1) if vo2 else None,
            "km_week": round(km4, 1) if acts else None,
            "level": level if acts else None,
        },
    }


# ---------- Prüfen ----------

def _int(v, lo, hi, name, required=True):
    if v in (None, ""):
        if required:
            raise SetupError(f"{name} fehlt.")
        return None
    try:
        x = int(round(float(v)))
    except (TypeError, ValueError):
        raise SetupError(f"{name}: keine gültige Zahl.") from None
    if not lo <= x <= hi:
        raise SetupError(f"{name}: bitte zwischen {lo} und {hi}.")
    return x


def _time(v, name, lo_sec, hi_sec, required=True):
    if not v:
        if required:
            raise SetupError(f"{name} fehlt.")
        return None
    v = str(v).strip()
    if not re.fullmatch(r"(\d{1,2}:)?\d{1,2}:\d\d", v):
        raise SetupError(f"{name}: bitte als mm:ss oder h:mm:ss angeben.")
    parts = [int(p) for p in v.split(":")]
    sec = parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]
    if not lo_sec <= sec <= hi_sec:
        raise SetupError(f"{name}: das wirkt unrealistisch, bitte prüfen.")
    return v


def plan_window(start: date, race: date | None) -> tuple[date, int, str | None]:
    """Startmontag und Wochenzahl. Mit Wettkampf endet der Plan in der Wettkampfwoche."""
    if not race:
        return start, 12, None
    race_monday = race - timedelta(days=race.weekday())
    n = (race_monday - start).days // 7 + 1
    if n < MIN_WEEKS:
        raise SetupError(f"Bis zum Wettkampf sind es nur {max(n, 0)} Wochen. Der Plan braucht mindestens {MIN_WEEKS}.")
    if n > MAX_WEEKS:
        start = race_monday - timedelta(weeks=MAX_WEEKS - 1)
        return start, MAX_WEEKS, f"Der Plan dauert höchstens {MAX_WEEKS} Wochen und startet deshalb am {start:%d.%m.%Y}. Bis dahin locker laufen."
    return start, n, None


def validate(ans: dict) -> tuple[dict, str | None]:
    name = str(ans.get("name") or "").strip()[:40]
    if not name:
        raise SetupError("Bitte gib deinen Namen an.")
    age = _int(ans.get("age"), 14, 90, "Alter")
    goal = ans.get("goal")
    if goal not in GOALS:
        raise SetupError("Bitte wähle ein Ziel.")
    five_k = _time(ans.get("five_k"), "5-km-Zeit", 12 * 60, 60 * 60)
    seen = suggestions()["suggest"]["hr_max_seen"] or 0
    hr_max = _int(ans.get("hr_max"), 140, 225, "Maximalpuls", required=False) or max(tanaka(age), min(seen, 225))
    hr_rest = _int(ans.get("hr_rest"), 30, 100, "Ruhepuls", required=False) or 60
    lthr = _int(ans.get("lthr"), 110, 210, "Schwellenpuls", required=False) or round(0.89 * hr_max)
    if not hr_rest < lthr < hr_max:
        raise SetupError("Pulswerte passen nicht zusammen: Ruhepuls < Schwellenpuls < Maximalpuls.")
    vo2 = ans.get("vo2max")
    vo2 = round(float(vo2), 1) if vo2 not in (None, "") else None
    if vo2 is not None and not 20 <= vo2 <= 90:
        raise SetupError("VO2max: bitte zwischen 20 und 90.")
    vo2_goal = ans.get("vo2max_goal")
    vo2_goal = round(float(vo2_goal), 1) if vo2_goal not in (None, "") else None
    if goal == "vo2max":
        if vo2 is None:
            raise SetupError("Für das Ziel VO2max brauche ich deinen aktuellen Garmin-VO2max.")
        vo2_goal = vo2_goal or vo2 + 3
        if not vo2 < vo2_goal <= vo2 + 8:
            raise SetupError("Ziel-VO2max: höher als der aktuelle Wert, aber höchstens 8 Punkte mehr.")
    elif vo2 is not None:
        vo2_goal = vo2_goal or round(vo2 + 2)

    run_days = _int(ans.get("run_days"), 3, 5, "Lauftage")
    level = _int(ans.get("level"), 0, 3, "Wochenumfang")
    long_day = ans.get("long_day") if ans.get("long_day") in ("Sa", "So") else "So"
    try:
        start = date.fromisoformat(ans.get("start") or next_monday().isoformat())
    except ValueError:
        raise SetupError("Startdatum ungültig.") from None
    start -= timedelta(days=start.weekday())  # immer ein Montag
    if start < date.today() - timedelta(days=6):
        raise SetupError("Der Start darf nicht in der Vergangenheit liegen.")
    race = None
    if goal != "vo2max" and ans.get("race_date"):
        try:
            race = date.fromisoformat(ans["race_date"])
        except ValueError:
            raise SetupError("Wettkampfdatum ungültig.") from None
    start, weeks, info = plan_window(start, race)
    lim = {"5k": (12 * 60, 60 * 60), "10k": (25 * 60, 2 * 3600), "half": (55 * 60, 4 * 3600)}.get(goal)
    goal_time = _time(ans.get("goal_time"), "Zielzeit", *lim, required=False) if lim else None

    loc = ans.get("location")
    if loc and not (isinstance(loc, dict) and isinstance(loc.get("lat"), (int, float)) and isinstance(loc.get("lon"), (int, float))):
        loc = None
    hour = _int(ans.get("training_hour"), 4, 23, "Trainingszeit", required=False)

    out = {
        "name": name, "age": age,
        "weight_kg": _int(ans.get("weight_kg"), 30, 250, "Gewicht", required=False),
        "height_cm": _int(ans.get("height_cm"), 120, 230, "Größe", required=False),
        "hr_rest": hr_rest, "hr_max": hr_max, "lthr": lthr, "five_k": five_k,
        "vo2max_start": vo2, "vo2max_goal": vo2_goal,
        "plan_start": start.isoformat(), "plan_intro_days": 0,
        "location": loc, "training_hour": hour if hour is not None else 18,
        "coach_context": str(ans.get("coach_context") or "").strip()[:2000],
        "training": {
            "goal": goal, "run_days": run_days, "strength": bool(ans.get("strength")), "bike": bool(ans.get("bike")),
            "long_day": long_day, "level": level, "race_date": race.isoformat() if race else None,
            "goal_time": goal_time, "weeks": weeks,
        },
    }
    return out, info


# ---------- Anwenden ----------

def apply(ans: dict) -> dict:
    values, info = validate(ans)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    old_athlete = ATHLETE_FILE.read_text(encoding="utf-8") if ATHLETE_FILE.exists() else None
    athlete = (json.loads(old_athlete) if old_athlete else {}) | values
    athlete.pop("_info", None)
    ATHLETE_FILE.parent.mkdir(parents=True, exist_ok=True)
    ATHLETE_FILE.write_text(json.dumps(athlete, indent=2, ensure_ascii=False), encoding="utf-8")

    backup = None
    if PLAN_FILE.exists():
        backup = PLAN_FILE.with_name(f"plan-{stamp}.json")
        shutil.copyfile(PLAN_FILE, backup)
    r = subprocess.run([sys.executable, "-m", "coach.plan_builder", "--force"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        if old_athlete is None:
            ATHLETE_FILE.unlink(missing_ok=True)
        else:
            ATHLETE_FILE.write_text(old_athlete, encoding="utf-8")
        if backup:
            shutil.copyfile(backup, PLAN_FILE)
        raise SetupError("Plan konnte nicht erstellt werden: " + (r.stderr.strip().splitlines() or ["unbekannter Fehler"])[-1])

    # Verschiebungen und Häkchen gehören zum alten Plan
    d = userdata.load()
    d["moves"], d["on_watch"] = {}, {}
    userdata.save(d)

    plan = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    _welcome_note(plan, values)
    return {"info": info, "backup": backup.name if backup else None, "goal": plan["goal"], "weeks": values["training"]["weeks"]}


def _welcome_note(plan: dict, v: dict) -> None:
    t = v["training"]
    rhythm = " · ".join(f"{r['day']} {r['name']}" for r in plan["rhythm"])
    first = next((s for s in plan["sessions"] if s["sport"] != "rest"), None)
    text = (f"Dein Plan für „{plan['goal']}“ steht: {t['weeks']} Wochen ab {date.fromisoformat(v['plan_start']):%d.%m.%Y}, "
            f"{t['run_days']} Lauftage pro Woche.\n\nWochenrhythmus: {rhythm}. Die Tage kannst du in der App verschieben, "
            "zwischen zwei harten Einheiten sollten mindestens 48 h liegen.\n\n"
            + (f"Los geht es am {date.fromisoformat(first['date']):%d.%m.} mit „{first['title']}“. " if first else "")
            + "Lockere Läufe wirklich locker, harte Einheiten mit Workout auf der Uhr. Dann kann ich jede Einheit genau auswerten.")
    notes = _load(NOTES_FILE, []) or []
    notes.insert(0, {"date": date.today().isoformat(), "title": "Dein neuer Plan", "text": text})
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    NOTES_FILE.write_text(json.dumps(notes[:10], indent=2, ensure_ascii=False), encoding="utf-8")
