"""Holt Daten über die offizielle Garmin Personal API und wertet FIT-Dateien aus."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime, timedelta
from typing import Any, Callable

from garmin_personal_api import (
    GarminPersonalApiClient,
    GarminPersonalApiError,
    PersonalApiAuthenticator,
    resolve_api_key,
)

from .config import DATA_DIR, FIT_DIR, SYNC_INFO_FILE, sport_of, zone_of

CHUNK_DAYS = 28
ACTIVITY_LOOKBACK = 120
HEALTH_LOOKBACK = 60


def _chunks(start: date, end: date):
    cur = start
    while cur <= end:
        e = min(cur + timedelta(days=CHUNK_DAYS - 1), end)
        yield cur, e
        cur = e + timedelta(days=1)


def _range(fn: Callable[[str, str], Any], start: date, end: date, unwrap: str | None = None) -> list:
    out: list = []
    for a, b in _chunks(start, end):
        res = fn(a.isoformat(), b.isoformat())
        if unwrap and isinstance(res, dict):
            res = res.get(unwrap) or []
        if isinstance(res, list):
            out.extend(res)
        elif res:
            out.append(res)
    return out


def _activities(c: GarminPersonalApiClient, start: date, end: date) -> list:
    out, off = [], 0
    while True:
        batch = c.search_activities(start=off, limit=50, start_date=start.isoformat(), end_date=end.isoformat())
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 50:
            break
        off += 50
    return out


def _save(name: str, payload: Any) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / f"{name}.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")


# ---------- FIT ----------

def parse_fit(raw: bytes, sport: str) -> dict:
    from garmin_fit_sdk import Decoder, Stream

    msgs, _ = Decoder(Stream.from_byte_array(bytearray(raw))).read()
    sess = (msgs.get("session_mesgs") or [{}])[0]
    start_ts = sess.get("start_time")

    laps = []
    for i, l in enumerate(msgs.get("lap_mesgs") or []):
        sec = l.get("total_timer_time") or 0
        dist = l.get("total_distance") or 0
        if sec < 5:
            continue
        laps.append({
            "i": i + 1,
            "intensity": str(l.get("intensity") or "active"),
            "trigger": str(l.get("lap_trigger") or ""),
            "sec": round(sec),
            "dist": round(dist),
            "pace_s": round(sec / dist * 1000) if dist > 50 else None,
            "avg_hr": l.get("avg_heart_rate"),
            "max_hr": l.get("max_heart_rate"),
            "avg_power": l.get("avg_power"),
            "cadence": (l.get("avg_running_cadence") or l.get("avg_cadence")),
        })

    zone_sec = [0, 0, 0, 0, 0]
    series = []
    prev = None
    for r in msgs.get("record_mesgs") or []:
        ts, hr = r.get("timestamp"), r.get("heart_rate")
        if ts is None:
            continue
        if prev is not None and hr:
            dt = (ts - prev).total_seconds()
            if 0 < dt <= 10:
                z = zone_of(hr, sport)
                if z:
                    zone_sec[z - 1] += dt
        prev = ts
        if start_ts and hr:
            t = int((ts - start_ts).total_seconds())
            if not series or t - series[-1][0] >= 10:
                spd = r.get("enhanced_speed") or r.get("speed")
                series.append([t, hr, round(spd, 2) if spd else None])

    vo2 = None
    for m in msgs.get(140) or msgs.get("140") or []:
        v = m.get(7)
        if isinstance(v, (int, float)) and v > 0:
            est = round(v * 3.5 / 65536, 1)
            if 25 <= est <= 90:
                vo2 = est

    wk = (msgs.get("workout_mesgs") or [{}])[0]
    rpe = sess.get("workout_rpe")
    return {
        "laps": laps,
        "zone_sec": [round(x) for x in zone_sec],
        "series": series,
        "vo2max": vo2 if sport == "run" else None,
        "rpe": round(rpe / 10) if isinstance(rpe, (int, float)) and rpe else None,
        "feel": sess.get("workout_feel"),
        "workout_name": wk.get("wkt_name"),
        "te_aer": sess.get("total_training_effect"),
        "te_ana": sess.get("total_anaerobic_training_effect"),
    }


def _fit_for(c: GarminPersonalApiClient, act: dict) -> dict:
    aid = act["activityId"]
    sport = sport_of(act["activityType"]["typeKey"])
    blob = c.download_activity(aid)
    z = zipfile.ZipFile(io.BytesIO(blob))
    name = next(n for n in z.namelist() if n.lower().endswith(".fit"))
    out = parse_fit(z.read(name), sport)
    out["activityId"] = aid
    return out


# ---------- Hauptfunktion ----------

def sync(activity_days: int = ACTIVITY_LOOKBACK, health_days: int = HEALTH_LOOKBACK, log=print) -> dict:
    today = date.today()
    a_start = today - timedelta(days=activity_days - 1)
    h_start = today - timedelta(days=health_days - 1)
    info: dict = {"last_sync": datetime.now().isoformat(timespec="seconds"), "ok": True, "errors": [], "new_fit": []}

    try:
        with PersonalApiAuthenticator() as auth:
            token = auth.obtain_token(resolve_api_key())
    except GarminPersonalApiError as exc:
        info.update(ok=False, errors=[f"Anmeldung fehlgeschlagen: {exc}"])
        SYNC_INFO_FILE.parent.mkdir(exist_ok=True)
        SYNC_INFO_FILE.write_text(json.dumps(info, indent=1), encoding="utf-8")
        return info

    jobs: dict[str, Callable[[GarminPersonalApiClient], Any]] = {
        "profile_settings": lambda c: c.get_user_profile_settings(),
        "heart_rate_zones": lambda c: c.get_heart_rate_zones(),
        "fitness_age": lambda c: c.get_fitness_age(today.isoformat()),
        "activities": lambda c: _activities(c, a_start, today),
        "daily_summaries": lambda c: _range(c.get_daily_summaries, h_start, today, unwrap="data"),
        "sleep_summaries": lambda c: _range(c.get_daily_sleep_summaries, h_start, today),
        "hrv": lambda c: _range(c.get_daily_hrv_summaries, h_start, today, unwrap="hrvSummaries"),
        "body_battery": lambda c: _range(c.get_daily_body_battery, h_start, today),
    }

    with GarminPersonalApiClient(token.access_token) as c:
        acts = []
        for name, job in jobs.items():
            try:
                res = job(c)
                _save(name, res)
                if name == "activities":
                    acts = res
                log(f"OK    {name:<17} {len(res) if isinstance(res, list) else 1}")
            except GarminPersonalApiError as exc:
                info["errors"].append(f"{name}: {str(exc)[:160]}")
                log(f"FEHLER {name}: {str(exc)[:160]}")

        FIT_DIR.mkdir(parents=True, exist_ok=True)
        for a in acts:
            f = FIT_DIR / f"{a['activityId']}.json"
            if f.exists() or sport_of(a["activityType"]["typeKey"]) == "other":
                continue
            try:
                parsed = _fit_for(c, a)
                f.write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
                info["new_fit"].append(a["activityId"])
                log(f"FIT   {a['startTimeLocal'][:10]} {a.get('activityName')}")
            except Exception as exc:  # FIT-Fehler sollen den Sync nicht abbrechen
                info["errors"].append(f"FIT {a['activityId']}: {str(exc)[:160]}")

    info["ok"] = not info["errors"]
    SYNC_INFO_FILE.write_text(json.dumps(info, indent=1), encoding="utf-8")
    return info
