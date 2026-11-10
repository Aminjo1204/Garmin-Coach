"""Plan-Abgleich, automatische Einheiten-Analyse und Tagesform. Liefert den kompletten App-Zustand."""

from __future__ import annotations

import json
import math
import re
import statistics as st
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from . import userdata
from .store import read_text
from .config import (ATHLETE, DATA_DIR, EASY_CAP_BIKE, EASY_CAP_RUN, FEEDBACK_DIR, FIT_DIR, NOTES_FILE, PLAN_FILE,
                     PLAN_START, SYNC_INFO_FILE, THR_HI, THR_LO, VO2_HR, sport_of)

HFMAX_VO2 = VO2_HR  # Untergrenze VO2max-Bereich (Zone 5)


def _load(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(read_text(path))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def fmt_pace(sec: float | None) -> str | None:
    if not sec:
        return None
    sec = round(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def _pace_range(p: str | None) -> tuple[int, int] | None:
    if not p:
        return None
    vals = [int(m) * 60 + int(s) for m, s in re.findall(r"(\d):(\d\d)", p)]
    if not vals:
        return None
    return min(vals), max(vals)


def _flat(steps):
    for s in steps or []:
        if s["type"] == "repeat":
            for _ in range(s["times"]):
                yield from _flat(s["steps"])
        else:
            yield s


# ---------- Laden ----------

def load_all() -> dict:
    fits = {}
    if FIT_DIR.exists():
        for f in FIT_DIR.glob("*.json"):
            d = _load(f)
            if d:
                fits[d["activityId"]] = d
    feedback = {}
    if FEEDBACK_DIR.exists():
        for f in FEEDBACK_DIR.glob("*.json"):
            if f.stem.isdigit():
                d = _load(f)
                if d:
                    feedback[int(f.stem)] = d
    return {
        "plan": _load(PLAN_FILE, {}),
        "activities": _load(DATA_DIR / "activities.json", []),
        "daily": _load(DATA_DIR / "daily_summaries.json", []),
        "sleep": _load(DATA_DIR / "sleep_summaries.json", []),
        "hrv": _load(DATA_DIR / "hrv.json", []),
        "fits": fits,
        "feedback": feedback,
        "notes": _load(NOTES_FILE, []),
        "sync": _load(SYNC_INFO_FILE, {}),
        "user": userdata.load(),
    }


# ---------- Abgleich ----------

def match_sessions(sessions: list[dict], acts: list[dict]) -> dict[int, str]:
    """activityId → sessionId. Gleicher Tag zuerst, sonst ±2 Tage innerhalb derselben Planwoche."""
    by_id = {s["id"]: s for s in sessions}
    taken: dict[str, list[int]] = {}
    out: dict[int, str] = {}
    first = sessions[0]["date"] if sessions else "9999"
    for a in sorted(acts, key=lambda a: a["startTimeLocal"]):
        d = a["startTimeLocal"][:10]
        if d < first:
            continue
        sp = sport_of(a["activityType"]["typeKey"])
        same = [s for s in sessions if s["sport"] == sp and s["date"] == d]
        if same:
            sid = same[0]["id"]
            out[a["activityId"]] = sid
            taken.setdefault(sid, []).append(a["activityId"])
            continue
        ad = date.fromisoformat(d)
        cands = []
        for s in sessions:
            if s["sport"] != sp or s["id"] in taken:
                continue
            sd = date.fromisoformat(s["date"])
            delta = abs((sd - ad).days)
            if delta <= 2 and s["week"] == _week_of(sessions, d):
                cands.append((delta, s["id"]))
        if cands:
            sid = sorted(cands)[0][1]
            out[a["activityId"]] = sid
            taken.setdefault(sid, []).append(a["activityId"])
    _ = by_id
    return out


def _week_of(sessions, d: str):
    for s in sessions:
        if s["date"] == d:
            return s["week"]
    return None


# ---------- Analyse einer Einheit ----------

def _metrics(a: dict, fit: dict | None) -> dict:
    sp = sport_of(a["activityType"]["typeKey"])
    dur = (a.get("movingDuration") or a.get("duration") or 0)
    dist = a.get("distance") or 0
    zs = (fit or {}).get("zone_sec") or [0] * 5
    tot = sum(zs) or 1
    zp = [round(100 * z / tot) for z in zs]
    return {
        "sport": sp,
        "dur_min": round((a.get("duration") or 0) / 60),
        "dist_km": round(dist / 1000, 2) if dist else None,
        "pace_s": round(dur / dist * 1000) if sp == "run" and dist > 200 else None,
        "speed_kmh": round(dist / dur * 3.6, 1) if sp == "bike" and dist and dur else None,
        "avg_hr": a.get("averageHR"),
        "max_hr": a.get("maxHR"),
        "zone_pct": zp if sum(zs) else None,
        "zone_min": [round(z / 60, 1) for z in zs] if sum(zs) else None,
        "easy_pct": zp[0] + zp[1] if sum(zs) else None,
        "hard_pct": zp[3] + zp[4] if sum(zs) else None,
        "vo2_min": round(zs[4] / 60, 1) if sum(zs) else None,
        "rpe": (fit or {}).get("rpe"),
        "feel": (fit or {}).get("feel"),
        "vo2max": (fit or {}).get("vo2max"),
        "te_aer": a.get("aerobicTrainingEffect"),
        "te_ana": a.get("anaerobicTrainingEffect"),
    }


def _work_laps(fit: dict | None) -> list[dict]:
    laps = (fit or {}).get("laps") or []
    if not any(l["intensity"] in ("warmup", "rest", "recovery", "cooldown") for l in laps):
        return []  # kein strukturiertes Workout → keine Intervallrunden
    return [l for l in laps if l["intensity"] in ("active", "interval")]


def analyze(a: dict, fit: dict | None, s: dict | None, plan_first: str = "") -> dict:
    m = _metrics(a, fit)
    pts: list[dict] = []

    def add(level: str, text: str):
        pts.append({"level": level, "text": text})

    sp = m["sport"]
    pre = a["startTimeLocal"][:10] < plan_first
    kind = s["kind"] if s else ("pre" if pre else "extra")

    if not s:
        if not pre:
            add("info", "Zusätzliche Einheit, nicht im Plan.")
        if sp in ("run", "bike") and m["zone_pct"]:
            add("info", f"Verteilung: {m['easy_pct']} % locker (Z1–2), {m['zone_pct'][2]} % Tempo (Z3), "
                        f"{m['hard_pct']} % hart (Z4–5).")
        if not pre and sp == "run" and (m["hard_pct"] or 0) > 30:
            add("warn", f"{m['hard_pct']} % in Zone 4–5: eine zusätzliche harte Einheit kostet Erholung für die Schlüsseleinheiten.")
        work = _work_laps(fit)
        if work:
            m["reps"] = [{"n": i + 1, "sec": w["sec"], "pace": fmt_pace(w["pace_s"]), "avg_hr": w["avg_hr"],
                          "max_hr": w["max_hr"]} for i, w in enumerate(work)]

    # Dauer vs. Plan
    if s and s.get("duration_min") and kind not in ("race", "test"):
        ratio = m["dur_min"] / s["duration_min"]
        if ratio < 0.8 and kind in ("vo2", "short", "hills", "threshold", "tempo"):
            add("info", f"{m['dur_min']} min statt {s['duration_min']} min. Ein- und Auslaufen nicht zu kurz halten, "
                        "sie gehören zum Reiz und zur Erholung.")
        elif ratio < 0.8:
            add("warn", f"Mit {m['dur_min']} min deutlich kürzer als geplant ({s['duration_min']} min).")
        elif ratio > 1.3 and kind in ("easy", "long", "bike_z2"):
            add("info", f"Länger als geplant ({m['dur_min']} statt {s['duration_min']} min). Okay, aber nicht zur Gewohnheit machen.")
        else:
            add("ok", f"Umfang passt: {m['dur_min']} min (geplant {s['duration_min']}).")

    if kind in ("easy", "long", "bike_z2"):
        cap = EASY_CAP_BIKE if sp == "bike" else EASY_CAP_RUN
        ep = m["easy_pct"]
        if ep is None:
            pass
        elif ep >= 80:
            add("ok", f"{ep} % der Zeit in Zone 1–2. Genau richtig locker.")
        elif ep >= 60:
            add("warn", f"Nur {ep} % in Zone 1–2. Etwas zu flott, beim nächsten Mal Puls unter {cap} halten.")
        else:
            add("bad", f"Nur {ep} % in Zone 1–2. Das war eher ein Tempolauf. Lockere Einheiten müssen locker sein, sonst fehlt die Frische für die Intervalle.")
        if m["avg_hr"] and m["avg_hr"] > cap + 3:
            add("warn", f"Ø-Puls {m['avg_hr']:.0f} liegt über der Grundlagen-Obergrenze ({cap}).")

    if kind in ("vo2", "short", "hills"):
        work = _work_laps(fit)
        planned = [x for x in _flat(s["steps"]) if x["type"] == "work"]
        target = _pace_range(planned[0].get("pace")) if planned else None
        if kind == "short":
            work = [w for w in work if w["sec"] <= 45]
        if not work:
            add("info", "Keine Intervall-Runden erkannt. Starte das Workout auf der Uhr, dann kann ich jede Wiederholung einzeln bewerten.")
        else:
            m["reps"] = [{"n": i + 1, "sec": w["sec"], "pace": fmt_pace(w["pace_s"]), "avg_hr": w["avg_hr"],
                          "max_hr": w["max_hr"]} for i, w in enumerate(work)]
            if len(work) >= len(planned):
                add("ok", f"Alle {len(planned)} Wiederholungen geschafft.")
            else:
                add("warn", f"{len(work)} von {len(planned)} Wiederholungen.")
            paces = [w["pace_s"] for w in work if w["pace_s"]]
            if paces and target and kind != "hills":
                avg = st.mean(paces)
                if avg > target[1] + 8:
                    add("warn", f"Ø {fmt_pace(avg)}/km ist langsamer als das Ziel ({fmt_pace(target[0])}–{fmt_pace(target[1])}).")
                elif avg < target[0] - 10:
                    add("warn", f"Ø {fmt_pace(avg)}/km ist schneller als geplant. Etwas kontrollierter, sonst leidet die Qualität der letzten Wiederholungen.")
                else:
                    add("ok", f"Pace im Ziel: Ø {fmt_pace(avg)}/km.")
            if len(paces) >= 3 and kind != "short":
                drop = (paces[-1] - paces[0]) / paces[0]
                if drop > 0.05:
                    add("warn", f"Letzte Wiederholung {drop * 100:.0f} % langsamer als die erste. Das spricht für einen zu schnellen Start.")
                else:
                    add("ok", "Gleichmäßig durchgezogen, kein Einbruch hinten raus.")
            peaks = [w["max_hr"] for w in work if w["max_hr"]]
            if peaks and kind != "short" and s.get("key"):
                hit = sum(1 for p in peaks if p >= HFMAX_VO2)
                if hit >= max(1, len(peaks) // 2):
                    add("ok", f"VO2max-Bereich (≥ {HFMAX_VO2} bpm) in {hit} von {len(peaks)} Wiederholungen erreicht.")
                else:
                    add("warn", f"Puls nur in {hit} von {len(peaks)} Wiederholungen ≥ {HFMAX_VO2}. Der VO2max-Reiz war eher knapp.")
        if m["vo2_min"] is not None:
            lvl = "ok" if m["vo2_min"] >= 8 else "info"
            add(lvl, f"{m['vo2_min']} min im VO2max-Bereich (Zone 5). Ziel pro Einheit: 8–15 min.")

    if kind in ("threshold", "tempo", "progression"):
        work = _work_laps(fit)
        planned = [x for x in _flat(s["steps"]) if x["type"] == "work"]
        target = _pace_range(planned[-1].get("pace")) if planned else None
        if not work:
            add("info", "Keine Schwellen-Runden erkannt. Mit Workout auf der Uhr wird die Auswertung genauer.")
        else:
            m["reps"] = [{"n": i + 1, "sec": w["sec"], "pace": fmt_pace(w["pace_s"]), "avg_hr": w["avg_hr"],
                          "max_hr": w["max_hr"]} for i, w in enumerate(work)]
            hrs = [w["avg_hr"] for w in work if w["avg_hr"]]
            if hrs:
                h = st.mean(hrs)
                if h > THR_HI:
                    add("warn", f"Ø-Puls in den Blöcken {h:.0f}: über der Schwelle. Etwas langsamer, sonst wird es eine VO2max-Einheit.")
                elif h < THR_LO - 5:
                    add("info", f"Ø-Puls {h:.0f} eher Tempo als Schwelle. Darf ruhig etwas zügiger sein.")
                else:
                    add("ok", f"Ø-Puls {h:.0f} in den Blöcken: sauber an der Schwelle.")
            paces = [w["pace_s"] for w in work if w["pace_s"]]
            if paces and target:
                avg = st.mean(paces)
                if target[0] - 10 <= avg <= target[1] + 8:
                    add("ok", f"Pace Ø {fmt_pace(avg)}/km im Zielbereich.")
                else:
                    add("info", f"Pace Ø {fmt_pace(avg)}/km (Ziel {fmt_pace(target[0])}–{fmt_pace(target[1])}).")

    if kind == "test":
        laps = (fit or {}).get("laps") or []
        best = [l for l in laps if 4800 <= (l["dist"] or 0) <= 5300]
        if best:
            l = best[0]
            t = l["sec"] * 5000 / l["dist"]
            m["test_5k"] = f"{int(t // 60)}:{int(t % 60):02d}"
            add("ok", f"5-km-Zeit: {m['test_5k']} (Ø {fmt_pace(l['pace_s'])}/km, Ø-Puls {l['avg_hr']}).")
        else:
            add("info", "Testabschnitt nicht als eigene Runde erkannt. Drück beim nächsten Test zu Beginn und am Ende die Runden-Taste.")

    if kind == "race":
        planned = next((x for x in _flat(s["steps"]) if x["type"] == "work"), None)
        if m["dist_km"] and a.get("duration"):
            add("ok", f"Zielzeit {fmt_time(a['duration'])} für {m['dist_km']:.2f} km (Ø {fmt_pace(m['pace_s'])}/km).")
        target = _pace_range(planned.get("pace")) if planned else None
        if target and m["pace_s"]:
            if m["pace_s"] <= target[1]:
                add("ok", f"Schneller oder im Plan-Tempo ({fmt_pace(target[0])}–{fmt_pace(target[1])}/km). Stark!")
            else:
                add("info", f"Etwas langsamer als das Plan-Tempo ({fmt_pace(target[0])}–{fmt_pace(target[1])}/km).")

    if kind == "strength":
        add("ok", "Kraftreiz gesetzt." if m["dur_min"] >= 30 else "Kurze Einheit. Wenn möglich alle Übungen schaffen.")

    if m["rpe"]:
        add("info", f"Dein Anstrengungsgefühl (RPE): {m['rpe']}/10.")
    if m["vo2max"]:
        add("info", f"Garmin-VO2max-Schätzung nach diesem Lauf: {m['vo2max']}.")

    score = 100
    for p in pts:
        score -= {"warn": 12, "bad": 25}.get(p["level"], 0)
    score = max(0, score)
    rating = "Stark" if score >= 85 else "Gut" if score >= 70 else "Okay" if score >= 50 else "Daneben"
    if not s:
        score, rating = None, ("Vor Planstart" if pre else "Zusatz")
    return {"score": score, "rating": rating, "points": pts, "metrics": m, "kind": kind}



# ---------- Trainingslast (akut vs. chronisch) ----------

ACWR_LEVELS = [
    (0.8, "low", "Niedrig", "Weniger als gewohnt. Gut zur Erholung, auf Dauer geht aber Form verloren."),
    (1.3, "ok", "Optimal", "Belastung im grünen Bereich. So wird man fitter, ohne zu überziehen."),
    (1.5, "high", "Erhöht", "Belastung steigt schnell. Lockere Einheiten jetzt wirklich locker halten."),
    (99, "danger", "Zu schnell", "Deutlich mehr als gewohnt: erhöhtes Verletzungsrisiko. Umfang oder Intensität reduzieren."),
]


def activity_load(a: dict, fit: dict | None) -> float:
    """Edwards-TRIMP: Minuten je Zone × Zonennummer. Ohne Pulsdaten: Minuten × 1,5."""
    zs = (fit or {}).get("zone_sec") or []
    if sum(zs) > 0:
        return sum(sec / 60 * (i + 1) for i, sec in enumerate(zs))
    return (a.get("duration") or 0) / 60 * 1.5


def load_series(acts: list[dict], fits: dict, days: int = 56) -> dict:
    daily: dict[str, float] = {}
    for a in acts:
        d = a["startTimeLocal"][:10]
        daily[d] = daily.get(d, 0) + activity_load(a, fits.get(a["activityId"]))
    today = date.today()
    first = min(daily) if daily else today.isoformat()
    series = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        acute = sum(daily.get((d - timedelta(days=k)).isoformat(), 0) for k in range(7))
        chronic = sum(daily.get((d - timedelta(days=k)).isoformat(), 0) for k in range(28)) / 4
        enough = (d - date.fromisoformat(first)).days >= 27  # erst ab 4 Wochen Historie aussagekräftig
        series.append({"date": d.isoformat(), "load": round(daily.get(d.isoformat(), 0)),
                       "acute": round(acute), "chronic": round(chronic),
                       "acwr": round(acute / chronic, 2) if chronic > 0 and enough else None})
    t = series[-1]
    level = None
    if t["acwr"] is not None:
        for lim, key, name, text in ACWR_LEVELS:
            if t["acwr"] < lim:
                level = {"key": key, "name": name, "text": text}
                break
    return {"series": series, "today": {**t, "level": level}}


# ---------- Wettkampf-Prognose (VDOT nach Daniels) ----------

RACES = [("5 km", 5000), ("10 km", 10000), ("Halbmarathon", 21097.5)]


def vdot_from(dist_m: float, t_sec: float) -> float:
    t = t_sec / 60
    v = dist_m / t
    vo2 = -4.6 + 0.182258 * v + 0.000104 * v * v
    pct = 0.8 + 0.1894393 * math.exp(-0.012778 * t) + 0.2989558 * math.exp(-0.1932605 * t)
    return vo2 / pct


def time_for(vdot: float, dist_m: float) -> float:
    lo, hi = dist_m / 1000 * 120, dist_m / 1000 * 900  # 2:00–15:00 min/km
    for _ in range(60):
        mid = (lo + hi) / 2
        if vdot_from(dist_m, mid) > vdot:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fmt_time(sec: float) -> str:
    sec = round(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _mmss_to_sec(x: str) -> int:
    parts = [int(p) for p in x.split(":")]
    return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0] * 3600 + parts[1] * 60 + parts[2]


def prediction(vo2: list[dict], tests: list[dict]) -> dict | None:
    """Basis = echte 5-km-Leistung (letzter Test, sonst five_k aus athlete.json), skaliert mit der VO2max-Veränderung."""
    if tests:
        ref = tests[-1]
        ref_time, ref_date, source = _mmss_to_sec(ref["time"]), ref["date"], f"5-km-Test vom {ref['date']}"
    elif ATHLETE.get("five_k"):
        ref_time, ref_date, source = _mmss_to_sec(ATHLETE["five_k"]), None, "5-km-Zeit aus deinem Profil"
    else:
        return None
    # VO2max zum Zeitpunkt der Referenz: Ø der Werte in den 14 Tagen davor (sonst Startwert aus dem Profil)
    if ref_date:
        win = [v["value"] for v in vo2 if ref_date >= v["date"] >= (date.fromisoformat(ref_date) - timedelta(days=14)).isoformat()]
    else:
        start = PLAN_START.isoformat()
        win = [v["value"] for v in vo2 if v["date"] <= start][-4:]
    ref_vo2 = st.mean(win) if win else float(ATHLETE.get("vo2max_start") or 0)
    if not ref_vo2:
        return None
    cur_vo2 = st.mean([v["value"] for v in vo2[-3:]]) if vo2 else ref_vo2
    goal_vo2 = float(ATHLETE.get("vo2max_goal") or cur_vo2)
    ref_vdot = vdot_from(5000, ref_time)

    def times(v):
        vd = ref_vdot * v / ref_vo2
        return {name: round(time_for(vd, d)) for name, d in RACES}

    now, goal = times(cur_vo2), times(goal_vo2)
    trend = [{"date": v["date"], "t5k": round(time_for(ref_vdot * v["value"] / ref_vo2, 5000))} for v in vo2[-40:]]
    return {
        "source": source, "ref_time": fmt_time(ref_time), "ref_vo2": round(ref_vo2, 1), "ref_vdot": round(ref_vdot, 1),
        "cur_vo2": round(cur_vo2, 1), "goal_vo2": goal_vo2, "vdot_now": round(ref_vdot * cur_vo2 / ref_vo2, 1),
        "races": [{"name": n, "now": now[n], "now_fmt": fmt_time(now[n]), "goal": goal[n], "goal_fmt": fmt_time(goal[n]),
                   "gain_fmt": fmt_time(now[n] - goal[n])} for n, _ in RACES],
        "trend": trend,
    }

# ---------- Tagesform ----------

def readiness_series(data: dict, days: int = 42) -> list[dict]:
    daily = {d["calendarDate"]: d for d in data["daily"]}
    sleep = {s["calendarDate"]: s for s in data["sleep"]}
    hrv = {h["calendarDate"]: h for h in data["hrv"]}
    out = []
    today = date.today()
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        ds, sl, hv = daily.get(d, {}), sleep.get(d, {}), hrv.get(d, {})
        bb = (ds.get("bodyBattery") or {})
        out.append({
            "date": d,
            "hrv": hv.get("lastNightAvg"),
            "hrv_week": hv.get("weeklyAvg"),
            "hrv_low": (hv.get("baseline") or {}).get("balancedLow"),
            "hrv_high": (hv.get("baseline") or {}).get("balancedUpper"),
            "hrv_status": hv.get("status"),
            "rhr": (ds.get("heartRate") or {}).get("restingValue"),
            "sleep_h": round(sl["sleepTimeSeconds"] / 3600, 1) if sl.get("sleepTimeSeconds") else None,
            "sleep_score": ((sl.get("sleepScores") or {}).get("overall") or {}).get("value"),
            "bb_max": bb.get("maxValue"),
        })
    return out


def readiness_today(series: list[dict], session: dict | None, acwr: float | None = None) -> dict:
    t = series[-1] if series else {}
    prev = [x["rhr"] for x in series[-15:-1] if x["rhr"]]
    score = 70
    factors = []

    if t.get("hrv"):
        low, status = t.get("hrv_low"), t.get("hrv_status")
        if status == "LOW" or (low and t["hrv"] < low - 5):
            score -= 20
            factors.append(("bad", f"HRV {t['hrv']} ms, deutlich unter deinem Normalbereich ({low}–{t.get('hrv_high')})"))
        elif low and t["hrv"] < low:
            score -= 8
            factors.append(("warn", f"HRV {t['hrv']} ms, knapp unter dem Normalbereich"))
        else:
            score += 10
            factors.append(("ok", f"HRV {t['hrv']} ms, im Normalbereich"))
    if t.get("rhr") and prev:
        base = st.mean(prev)
        diff = t["rhr"] - base
        if diff >= 5:
            score -= 15
            factors.append(("bad", f"Ruhepuls {t['rhr']}, {diff:+.0f} über deinem Schnitt"))
        elif diff >= 3:
            score -= 6
            factors.append(("warn", f"Ruhepuls {t['rhr']}, leicht erhöht ({diff:+.0f})"))
        else:
            score += 5
            factors.append(("ok", f"Ruhepuls {t['rhr']}, normal"))
    if t.get("sleep_score"):
        s = t["sleep_score"]
        if s < 60:
            score -= 12
            factors.append(("bad", f"Schlaf-Score {s} ({t.get('sleep_h')} h)"))
        elif s < 75:
            factors.append(("warn", f"Schlaf-Score {s} ({t.get('sleep_h')} h)"))
        else:
            score += 8
            factors.append(("ok", f"Schlaf-Score {s} ({t.get('sleep_h')} h)"))
    if t.get("bb_max"):
        b = t["bb_max"]
        if b < 40:
            score -= 10
            factors.append(("bad", f"Body Battery max. {b}"))
        elif b >= 70:
            score += 5
            factors.append(("ok", f"Body Battery max. {b}"))
        else:
            factors.append(("warn", f"Body Battery max. {b}"))

    if acwr is not None and acwr >= 1.5:
        score -= 10
        factors.append(("bad", f"Trainingslast {acwr:.2f}× über deinem Schnitt (Belastungsampel rot)"))
    elif acwr is not None and acwr >= 1.3:
        factors.append(("warn", f"Trainingslast {acwr:.2f}× über deinem Schnitt"))

    score = max(0, min(100, score))
    level = "green" if score >= 70 else "yellow" if score >= 50 else "red"
    key = bool(session and session.get("key"))
    hard = bool(session and session.get("sport") in ("run", "bike", "strength"))
    if not factors:
        advice = "Noch keine Erholungsdaten für heute. Uhr synchronisieren und dann neu laden."
    elif session is None:
        advice = {"green": "Gut erholt.", "yellow": "Erholung mittel. Heute nichts Hartes einbauen.",
                  "red": "Dein Körper braucht Erholung."}[level] + " Heute steht nichts im Plan."
    elif level == "green":
        advice = "Du bist bereit. Zieh die Einheit wie geplant durch." if hard else "Gute Erholung. Genieß den Ruhetag."
    elif level == "yellow":
        advice = ("Einheit machen, aber auf den Körper hören: Fühlt sich die erste Wiederholung zäh an, lass eine weg."
                  if key else "Normal trainieren, aber eher am unteren Ende der Pulsvorgaben.")
    else:
        advice = ("Heute tauschen: 30–40 min locker statt der Schlüsseleinheit. Die harte Einheit verschiebt sich um 1–2 Tage."
                  if key else "Heute kürzer und sehr locker, oder ganz frei. Erholung hat Vorrang.")
    return {"date": t.get("date"), "score": score, "level": level, "factors": factors, "advice": advice}


# ---------- Gesamtzustand ----------

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def apply_moves(sessions: list[dict], moves: dict) -> list[dict]:
    """Vom Athleten in der App verschobene Einheiten auf ihr neues Datum legen (id bleibt gleich)."""
    out = []
    for s in sessions:
        new = moves.get(s["id"])
        if new and new != s["date"]:
            s = dict(s, date=new, weekday=WEEKDAYS[date.fromisoformat(new).weekday()], moved_from=s["date"])
        out.append(s)
    return sorted(out, key=lambda s: (s["date"], s["sport"] == "rest"))


def build_state() -> dict:
    data = load_all()
    plan = data["plan"]
    sessions = apply_moves(plan.get("sessions", []), userdata.values(data["user"], "moves"))
    today = date.today().isoformat()
    acts = [a for a in data["activities"] if sport_of(a["activityType"]["typeKey"]) != "other"]
    link = match_sessions(sessions, acts)
    sess_by_id = {s["id"]: s for s in sessions}

    out_acts = []
    for a in sorted(acts, key=lambda a: a["startTimeLocal"], reverse=True):
        aid = a["activityId"]
        fit = data["fits"].get(aid)
        s = sess_by_id.get(link.get(aid)) if aid in link else None
        an = analyze(a, fit, s, sessions[0]["date"] if sessions else "")
        out_acts.append({
            "id": aid,
            "date": a["startTimeLocal"][:10],
            "start": a["startTimeLocal"],
            "name": a.get("activityName"),
            "type": a["activityType"]["typeKey"],
            "session_id": s["id"] if s else None,
            "session_title": s["title"] if s else None,
            "analysis": an,
            "feedback": data["feedback"].get(aid),
            "athlete_note": (data["user"]["notes"].get(str(aid)) or {}).get("value"),
            "athlete_note_at": (data["user"]["notes"].get(str(aid)) or {}).get("at"),
        })

    act_by_session: dict[str, list] = {}
    for a in out_acts:
        if a["session_id"]:
            act_by_session.setdefault(a["session_id"], []).append(a["id"])

    out_sessions = []
    for s in sessions:
        s = dict(s)
        s["activity_ids"] = act_by_session.get(s["id"], [])
        if s["sport"] == "rest":
            s["status"] = "rest"
        elif s["activity_ids"]:
            s["status"] = "done"
        elif s["date"] < today:
            s["status"] = "missed"
        elif s["date"] == today:
            s["status"] = "today"
        else:
            s["status"] = "planned"
        out_sessions.append(s)

    weeks = []
    for w in plan.get("weeks", []):
        ws = [s for s in out_sessions if s["week"] == w["week"]]
        done_acts = [a for a in out_acts if a["session_id"] in {s["id"] for s in ws}]
        due = [s for s in ws if s["sport"] != "rest" and s["date"] <= today]
        w = dict(w)
        w["done_run_km"] = round(sum(a["analysis"]["metrics"]["dist_km"] or 0 for a in done_acts
                                     if a["analysis"]["metrics"]["sport"] == "run"), 1)
        w["done_min"] = sum(a["analysis"]["metrics"]["dur_min"] for a in done_acts)
        w["sessions_due"] = len(due)
        w["sessions_done"] = sum(1 for s in due if s["status"] == "done")
        weeks.append(w)

    series = readiness_series(data)
    load = load_series(acts, data["fits"])
    today_session = next((s for s in out_sessions if s["date"] == today and s["sport"] != "rest"), None) or \
        next((s for s in out_sessions if s["date"] == today), None)

    vo2 = []
    for a in sorted(acts, key=lambda a: a["startTimeLocal"]):
        v = (data["fits"].get(a["activityId"]) or {}).get("vo2max")
        if v:
            vo2.append({"date": a["startTimeLocal"][:10], "value": v})

    tests = [{"date": a["date"], "time": a["analysis"]["metrics"]["test_5k"]} for a in reversed(out_acts)
             if a["analysis"]["metrics"].get("test_5k")]

    run_recent = [a for a in out_acts if a["analysis"]["metrics"]["sport"] == "run"
                  and a["date"] >= (date.today() - timedelta(days=28)).isoformat()
                  and a["analysis"]["metrics"]["zone_min"]]
    zone_4w = [round(sum(a["analysis"]["metrics"]["zone_min"][i] for a in run_recent)) for i in range(5)]

    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "today": today,
        "setup_needed": not plan.get("sessions"),
        "athlete": ATHLETE,
        "goal": plan.get("goal"),
        "sync": data["sync"],
        "plan": {k: plan.get(k) for k in ("start", "phases", "zones", "paces", "changelog", "rhythm", "goal_id",
                                          "training")} |
                {"weeks": weeks, "sessions": out_sessions},
        "activities": out_acts,
        "readiness": {"today": readiness_today(series, today_session, load["today"]["acwr"]), "series": series},
        "load": load,
        "vo2": vo2,
        "zone_4w": zone_4w,
        "prediction": prediction(vo2, tests),
        "notes": data["notes"],
    }


def activity_detail(aid: int) -> dict | None:
    fit = _load(FIT_DIR / f"{aid}.json")
    return fit
